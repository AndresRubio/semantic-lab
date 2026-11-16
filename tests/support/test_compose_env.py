from tests.support.compose_env import without_lab_settings


def test_every_lab_setting_is_removed_and_the_rest_is_kept() -> None:
    environ = {
        "SEMANTIC_LAB_POSTGRES_PORT": "5440",
        "SEMANTIC_LAB_CUBE_SECRET": "from-the-shell",
        "SEMANTIC_LAB_": "bare prefix",
        "PATH": "/usr/bin",
        "HOME": "/home/lab",
        "DOCKER_HOST": "unix:///var/run/docker.sock",
        "NOT_SEMANTIC_LAB_X": "kept",
        "semantic_lab_lower": "kept",
    }
    assert without_lab_settings(environ) == {
        "PATH": "/usr/bin",
        "HOME": "/home/lab",
        "DOCKER_HOST": "unix:///var/run/docker.sock",
        "NOT_SEMANTIC_LAB_X": "kept",
        "semantic_lab_lower": "kept",
    }


def test_the_mapping_it_was_given_is_left_as_it_was() -> None:
    environ = {"SEMANTIC_LAB_POSTGRES_PORT": "5440", "PATH": "/usr/bin"}
    without_lab_settings(environ)
    assert environ == {"SEMANTIC_LAB_POSTGRES_PORT": "5440", "PATH": "/usr/bin"}
