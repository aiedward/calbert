import logging
import pytest
import tempfile
import glob
import argparse
from pathlib import Path

from omegaconf import OmegaConf
from calbert import tokenizer


def train_tokenizer(
    input_file_and_outdir: (str, str)
) -> (tokenizer.CalbertTokenizer, str):
    input_file, outdir = input_file_and_outdir
    args, cfg = tokenizer_args_and_cfg(input_file, outdir)

    return tokenizer.train(args, cfg), outdir


def tokenizer_args_and_cfg(
    input_file: str, outdir: str
) -> (argparse.Namespace, OmegaConf):
    args = tokenizer.arguments().parse_args(
        ["--input-file", input_file, "--out-dir", outdir]
    )
    config = [
        "vocab.size=10",
        "vocab.min_frequency=2",
        "vocab.lowercase=True",
    ]
    cfg = OmegaConf.from_dotlist(config)
    return args, cfg


training_text = [
    "Porto posat l'esquinç al peu sense sutura marejant metges i perdius i això no es cura.",
    "La sang s’ha cuit fins a tornar-se dura i passa el temps i passa i això no es cura.",
    "Camí de massa ampla tessitura estintolada, encara sobre la corda insegura.",
]

validation_text = ["La corda insegura s'ha cuit"]


@pytest.fixture(scope="module")
def input_file_and_outdir(which="train") -> (str, str):
    with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8") as input_file:
        with tempfile.TemporaryDirectory() as outdir:
            for text in training_text if which == "train" else validation_text:
                input_file.write(text + "\n")
            filename = input_file.name
            input_file.flush()
            yield filename, outdir


@pytest.mark.describe("tokenizer.CalbertTokenizer")
class TestCalbertokenizer:
    @pytest.mark.it("Trains a tokenizer on some corpus")
    def test_train(self, input_file_and_outdir):
        t, outdir = train_tokenizer(input_file_and_outdir)

        assert len(t) == 38
        assert t.id_to_token(0) == "<unk>"
        assert t.id_to_token(1) == "<pad>"
        assert t.id_to_token(2) == "[MASK]"
        assert t.id_to_token(3) == "[SEP]"
        assert t.id_to_token(4) == "[CLS]"

    @pytest.mark.it("Encodes single sentences BERT-style with CLS and SEP")
    def test_single_sentence_encoding(self, input_file_and_outdir):
        t, outdir = train_tokenizer(input_file_and_outdir)
        encoded = t.process("hola com anem")
        assert t.id_to_token(encoded.ids[0]) == "[CLS]"
        assert t.id_to_token(encoded.ids[-1]) == "[SEP]"

    @pytest.mark.it("Encodes pairs of sentences BERT-style with CLS and SEP")
    def test_sentence_pair_encoding(self, input_file_and_outdir):
        t, outdir = train_tokenizer(input_file_and_outdir)
        encoded = t.process("hola com anem", "molt be i tu")
        assert t.id_to_token(encoded.ids[0]) == "[CLS]"
        assert t.id_to_token(encoded.ids[15]) == "[SEP]"
        assert t.id_to_token(encoded.ids[-1]) == "[SEP]"

    @pytest.mark.it("Truncates encodings to a max sequence length")
    def test_truncates_encodings(self, input_file_and_outdir):
        t, outdir = train_tokenizer(input_file_and_outdir)

        encoded = t.process("hola com anem", max_seq_len=12)
        assert encoded.tokens[-1] == "a"

    @pytest.mark.it("Pads encodings up to a max sequence length")
    def test_pads_encodings(self, input_file_and_outdir):
        t, outdir = train_tokenizer(input_file_and_outdir)

        encoded = t.process("hola com anem", max_seq_len=100)
        assert encoded.tokens[-1] == "<pad>"

    @pytest.mark.it("Saves the tokenizer's vocab and merges")
    def test_saves_tokenizer(self, input_file_and_outdir):
        _, outdir = train_tokenizer(input_file_and_outdir)

        assert glob.glob(outdir + "/*") == [
            outdir + "/ca.bpe.38-vocab.json",
            outdir + "/ca.bpe.38-merges.txt",
        ]

    @pytest.mark.it("Encodes to a tensor with encoding_to_tensor")
    def test_encoding_to_tensor(self, input_file_and_outdir):
        t, outdir = train_tokenizer(input_file_and_outdir)

        e = t.process("hello", max_seq_len=10)
        tensor = tokenizer.encoding_to_tensor(e)

        assert tensor.shape == (4, 10)

        assert tensor[0].tolist() == e.ids
        assert tensor[1].tolist() == e.special_tokens_mask
        assert tensor[2].tolist() == e.attention_mask
        assert tensor[3].tolist() == e.type_ids
