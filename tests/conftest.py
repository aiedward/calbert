import tempfile

training_text = [
    "Porto posat l'esquinç al peu sense sutura marejant metges i perdius i això no es cura.",
    "La sang s’ha cuit fins a tornar-se dura i passa el temps i passa i això no es cura.",
    "Camí de massa ampla tessitura estintolada, encara sobre la corda insegura.",
    "Hola",
]

validation_text = ["La corda insegura s'ha cuit malament"]


class InputData:
    def __init__(self, which="train"):
        self.which = which
        self.file = tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8")

    def __enter__(self, **args):
        self.file.__enter__(**args)
        for text in training_text if self.which == "train" else validation_text:
            self.file.write(text + "\n")
        self.file.flush()
        return self.file.name

    def __exit__(self, exc_type, exc_value, tb):
        self.file.__exit__(exc_type, exc_value, tb)


def folder():
    return tempfile.TemporaryDirectory()
