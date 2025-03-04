def test_docker_runs(docker):
    exit_code, output = docker.exec_run("/example-app")
    assert 0 == exit_code
    assert "Hello!" in output.decode()
