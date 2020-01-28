from pathlib import Path

import torch
import wandb
from fastai2.basics import random, rank_distrib, num_distrib
from fastai2.callback.wandb import WandbCallback, wandb_process
from transformers import AlbertForMaskedLM

from calbert.tokenizer import CalbertTokenizer


def cleanup(text: str):
    return text.replace("[CLS] ", "").replace("[SEP]", "")


class WandbReporter(WandbCallback):
    def __init__(
        self,
        tokenizer: CalbertTokenizer,
        ignore_index: int,
        model_class,
        log_examples_html=False,
        **kwargs
    ):
        super(WandbReporter, self).__init__(**kwargs)
        self.tokenizer = tokenizer
        self.log_examples_html = log_examples_html
        self.ignore_index = ignore_index
        self.model_class = model_class

    def begin_fit(self):
        "Call watch method to log model topology, gradients & weights"
        self.run = (
            not hasattr(self.learn, "lr_finder")
            and not hasattr(self, "gather_preds")
            and rank_distrib() == 0
        )
        if not self.run:
            return
        if not WandbCallback._wandb_watch_called:
            WandbCallback._wandb_watch_called = True
            # Logs model topology and optionally gradients and weights
            wandb.watch(self.learn.model, log=self.log)

        if hasattr(self, "save_model"):
            self.save_model.add_save = Path(wandb.run.dir) / "bestmodel.pth"

        if self.log_preds and not self.valid_dl:
            # Initializes the batch watched
            wandbRandom = random.Random(self.seed)  # For repeatability
            self.n_preds = min(self.n_preds, len(self.dls.valid_ds))
            idxs = wandbRandom.sample(range(len(self.dls.valid_ds)), self.n_preds)

            items = [self.dls.valid_ds[i] for i in idxs]
            self.valid_dl = self.dls.valid.new(items=items, bs=self.n_preds, rank=rank_distrib(), world_size=num_distrib())

    def after_epoch(self):
        "Log validation loss and custom metrics"
        # Correct any epoch rounding error and overwrite value
        self._wandb_epoch = round(self._wandb_epoch)

        report = {"epoch": self._wandb_epoch}

        if self.log_preds:
            b = self.valid_dl.one_batch()
            if isinstance(b, tuple):
                self.learn.model.__class__ = AlbertForMaskedLM

                loss, prediction_scores = self.learn.model(
                    b[0],
                    masked_lm_labels=b[1],
                    attention_mask=b[2],
                    token_type_ids=b[3],
                )

                self.learn.model.__class__ = self.model_class

                predicted = torch.argmax(prediction_scores, dim=2).tolist()

                encoded_sentences = b[0].tolist()
                encoded_answers = b[1].tolist()

                examples = []
                formatted_examples = []

                for stc_idx, sentence in enumerate(encoded_sentences):
                    stc = [t for t in sentence if t != 1]  # ignore padding at the end
                    answer = encoded_answers[stc_idx][0 : len(stc)]

                    right_answer = [
                        t[0] if t[1] == self.ignore_index else t[1]
                        for t in zip(stc, answer)
                    ]

                    words_to_emphasize_in_correct = []
                    words_to_emphasize_in_predicted = []

                    for tkn_idx, token in enumerate(predicted[stc_idx][0 : len(stc)]):
                        if answer[tkn_idx] != self.ignore_index:
                            correct_word = self.tokenizer.decode([answer[tkn_idx]])
                            predicted_word = self.tokenizer.decode([token])

                            words_to_emphasize_in_correct.append(correct_word)
                            words_to_emphasize_in_predicted.append(predicted_word)

                            stc[tkn_idx] = token

                    predicted_s = cleanup(self.tokenizer.decode(stc))
                    correct_s = cleanup(self.tokenizer.decode(right_answer))

                    examples.append([correct_s, predicted_s])

                    for word in words_to_emphasize_in_predicted:
                        predicted_s = predicted_s.replace(
                            word, "<strong>" + word + "</strong>"
                        )

                    for word in words_to_emphasize_in_correct:
                        correct_s = correct_s.replace(
                            word, "<strong>" + word + "</strong>"
                        )

                    formatted_examples.append([correct_s, predicted_s])
                    predicted_s = ""
                    correct_s = ""

                if self.log_examples_html:
                    html = (
                        "<html><head></head><body><dl>"
                        + "<br/>".join(
                            [
                                "<dt>" + e[0] + "</dt><dd>" + e[1] + "</dd>"
                                for e in formatted_examples
                            ]
                        )
                        + "</dl></body></html>"
                    )
                    report.update(
                        {
                            "Prediction Examples (HTML)": wandb.Html(
                                data=html, inject=True
                            )
                        },
                    )
                else:
                    report.update(
                        {
                            "Prediction Examples": wandb.Table(
                                data=examples, columns=["Correct", "Predicted"]
                            )
                        }
                    )

        metric_names = list(self.recorder.metric_names).copy()
        values = list(self.recorder.log).copy()

        if len(values) != len(
            metric_names
        ):  # learn.validate() means there is no train_loss
            del metric_names[metric_names.index("train_loss")]

        report.update(
            {
                n: s
                for n, s in zip(metric_names, values)
                if n not in ["train_loss", "epoch", "time"]
            }
        )

        wandb.log(
            report, step=self._wandb_step,
        )
