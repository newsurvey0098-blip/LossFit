from backend.app.environment import load_project_environment


def test_local_file_overrides_project_defaults_but_not_process_environment(tmp_path):
    environment = {"ENVIRONMENT": "development", "LOSSFIT_ENV_PROCESS": "process"}
    (tmp_path / ".env.local").write_text(
        "LOSSFIT_ENV_LOCAL=local\nLOSSFIT_ENV_OVERRIDE=local\nLOSSFIT_ENV_PROCESS=file-local\n",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        "LOSSFIT_ENV_BASE=base\nLOSSFIT_ENV_OVERRIDE=base\nLOSSFIT_ENV_PROCESS=file-base\n",
        encoding="utf-8",
    )

    load_project_environment(tmp_path, environment)

    assert environment["LOSSFIT_ENV_LOCAL"] == "local"
    assert environment["LOSSFIT_ENV_BASE"] == "base"
    assert environment["LOSSFIT_ENV_OVERRIDE"] == "local"
    assert environment["LOSSFIT_ENV_PROCESS"] == "process"


def test_production_ignores_machine_specific_local_file(tmp_path):
    environment = {}
    (tmp_path / ".env.local").write_text("LOSSFIT_ENV_LOCAL_SECRET=developer-secret\n", encoding="utf-8")
    (tmp_path / ".env").write_text("ENVIRONMENT=production\nLOSSFIT_ENV_BASE=base\n", encoding="utf-8")

    load_project_environment(tmp_path, environment)

    assert "LOSSFIT_ENV_LOCAL_SECRET" not in environment
    assert environment["LOSSFIT_ENV_BASE"] == "base"


def test_process_production_setting_also_ignores_local_file(tmp_path):
    environment = {"ENVIRONMENT": "production"}
    (tmp_path / ".env.local").write_text("LOSSFIT_ENV_LOCAL_SECRET=developer-secret\n", encoding="utf-8")
    (tmp_path / ".env").write_text("LOSSFIT_ENV_BASE=base\n", encoding="utf-8")

    load_project_environment(tmp_path, environment)

    assert "LOSSFIT_ENV_LOCAL_SECRET" not in environment
    assert environment["LOSSFIT_ENV_BASE"] == "base"
