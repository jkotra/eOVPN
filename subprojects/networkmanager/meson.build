project('eovpn_nm', 'c')

main_project = 'eovpn'
main_project_id = 'com.hithub.jkotra.eovpn'

deps = [
    dependency('libnm'),
]

python = import('python')
python_instllation = python.find_installation()
python_dir = python_instllation.get_install_dir()
lib_install_dir = python_dir / main_project / 'networkmanager'
message(lib_install_dir)

libeovpn_nm = shared_library('eovpn_nm',
  'eovpn_nm.c',
  dependencies: deps,
  install : true,
  install_dir: lib_install_dir
)