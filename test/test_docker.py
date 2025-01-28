def test_docker_runs(docker):
    exit_code, output = docker.exec_run("echo -n Hello, World!")
    assert "Hello, World!" == output.decode()
