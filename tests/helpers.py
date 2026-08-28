from types import SimpleNamespace


class FakeArgs:
    def __init__(self, values=None):
        self.values = values or {}

    def has_arg(self, name):
        return name in self.values

    def get_arg(self, name):
        return self.values.get(name)


def make_task(arguments=None, build_parameters=None, secrets=None, task_id=100):
    build_parameters = build_parameters or {}
    return SimpleNamespace(
        args=FakeArgs(arguments),
        BuildParameters=[
            SimpleNamespace(Name=name, Value=value)
            for name, value in build_parameters.items()
        ],
        Task=SimpleNamespace(ID=task_id),
        Callback=SimpleNamespace(ID=1),
        Secrets=secrets or {},
    )


class FakeProcess:
    def __init__(self, returncode=0, stdout=b"", stderr=b""):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout, self._stderr
