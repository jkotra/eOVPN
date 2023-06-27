project('eovpn',
  version: '1.28.1',
  meson_version: '>= 0.60.0'
)

i18n = import('i18n')
python = import('python')
python_instllation = python.find_installation()

gnome = import('gnome')
project_id = 'com.github.jkotra.eovpn'


prefix = get_option('prefix') # should be /usr
bindir = get_option('bindir') # should be bin
datadir = get_option('datadir') # should be /usr/share
pkg_datadir = join_paths(prefix, datadir, meson.project_name())
schemas_dir = get_option('prefix') / get_option('datadir') / 'glib-2.0' / 'schemas'
python_dir = python_instllation.get_install_dir()

message(prefix)
message(python_dir)

locale_dir = join_paths(prefix, get_option('localedir'))
icondir = join_paths(datadir, 'icons/hicolor')

conf = configuration_data()
conf.set('PACKAGE_URL', 'https://github.com/jkotra/eovpn')
conf.set('DATA_DIR', datadir)
conf.set('PKG_DATADIR', pkg_datadir)
conf.set('LOCALE_DIR', join_paths(get_option('prefix'), get_option('datadir'), 'locale'))
conf.set('PYTHON_DIR', python_dir)

bin_exec = configure_file(
  input: 'eovpn.in',
  output: 'eovpn.py',
  configuration: conf,
)

install_data(
  bin_exec,
  install_dir: bindir,
  rename: 'eovpn'
)

subdir('eovpn')
subdir('po')
subdir('data')

subproject('networkmanager')
if get_option('openvpn3')
  subproject('openvpn3')
endif

install_subdir(
  'eovpn',
  install_dir: python_dir
)

meson.add_install_script('meson_post_install.py')