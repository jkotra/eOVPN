project('openvpn3', 'c')

main_project = 'eovpn'
main_project_id = 'com.hithub.jkotra.eovpn'

deps = [
    dependency('gio-unix-2.0'),
    dependency('glib-2.0')
]

python = import('python')
python_instllation = python.find_installation()
python_dir = python_instllation.get_install_dir()
lib_install_dir = python_dir / main_project / 'openpvn3'
message(lib_install_dir)

libeovpn_nm = shared_library('openvpn3',
  'openvpn3.c',
  dependencies: deps,
  install : true,
  install_dir: lib_install_dir
)