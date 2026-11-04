from backend_app.agent.structured_runner import run_codex_cli_structured


class CodexCliProviderAdapter:
    def __init__(self, provider, model_profile, base_dir, log=None):
        self.provider = provider
        self.model_profile = model_profile
        self.base_dir = base_dir
        self.log = log

    def run_structured(self, prompt, schema, timeout=None):
        options = self.model_profile.get("extra_options") or {}
        return run_codex_cli_structured(
            prompt,
            schema,
            base_dir=self.base_dir,
            codex_cmd=options.get("executable") or "codex",
            codex_model=self.model_profile["model_name"],
            timeout=timeout or self.provider.get("timeout_seconds") or 180,
            log=self.log,
        )
