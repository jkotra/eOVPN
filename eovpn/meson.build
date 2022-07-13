r = run_command('git', 'rev-parse', 'HEAD', check: true)
commit_hash = r.stdout().strip()

message('current commit', commit_hash)

conf = configuration_data()
conf.set('VERSION', meson.project_version())
conf.set('COMMIT', commit_hash)

configure_file(
  input: 'metadata.json.in',
  output: 'metadata.json',
  configuration: conf,
  install: true,
  install_dir: python_dir / meson.project_name()
)

message('metadata.json generated!')