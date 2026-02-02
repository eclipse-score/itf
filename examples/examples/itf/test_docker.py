def test_docker_runs(target):
    exit_code, output = target.exec_run("/example-app")
    assert 0 == exit_code
    assert "Hello!" in output.decode()
