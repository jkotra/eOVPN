project('eovpn_nm', 'c')

main_project = 'eovpn'
main_project_id = 'com.hithub.jkotra.eovpn'

deps = [
    dependency('libnm'),
]

python = import('python')
python_exe = python.find_installation()
python_dir = python_exe.get_install_dir()
lib_install_dir = python_dir / main_project / 'backend' / 'networkmanager'
message(lib_install_dir)

libeovpn_nm = shared_library('eovpn_nm',
    'eovpn_nm.c',
    dependencies: deps,
    install : true,
    install_dir: lib_install_dir
)


ffi = custom_target(
    input: libeovpn_nm,
    output: '_libeovpn_nm.so',
    command: [python_exe, meson.source_root() / 'cffi_compile.py' ,
    '--library', libeovpn_nm,
    '--header', meson.current_source_dir() / 'eovpn_nm.h',
    ],
    install : true, 
    depends: libeovpn_nm,
    install_dir : lib_install_dir
)