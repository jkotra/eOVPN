project('eovpn',
  version: '0.01',
  meson_version: '>= 0.47.0'
)

i18n = import('i18n')
python = import('python3')
gnome = import('gnome')
project_id = 'com.github.jkotra.eovpn'


prefix = get_option('prefix') # should be /usr
bindir = get_option('bindir') # should be bin
datadir = get_option('datadir') # should be /usr/share

message(prefix)

pkg_datadir = join_paths(prefix, datadir, meson.project_name())
python_dir = join_paths(prefix, python.sysconfig_path('purelib'))
locale_dir = join_paths(prefix, get_option('localedir'))
icondir = join_paths(datadir, 'icons/hicolor')

# Dependencies
dependency('gobject-introspection-1.0', version: '>= 1.35.0')
dependency('gtk+-3.0', version: '>= 3.22')
dependency('glib-2.0')
dependency('pygobject-3.0', version: '>= 3.29.1')


conf = configuration_data()
conf.set('PACKAGE_URL', 'https://github.com/jkotra/eovpn')
conf.set('DATA_DIR', datadir)
conf.set('PKG_DATADIR', pkg_datadir)
conf.set('LOCALE_DIR', join_paths(get_option('prefix'), get_option('datadir'), 'locale'))
conf.set('PYTHON_DIR', python_dir)


subdir('data')
install_subdir(
  'eovpn',
  install_dir: python_dir
)


configure_file(
  input: 'eovpn.in',
  output: 'eovpn',
  configuration: conf,
  install_dir: bindir
)

meson.add_install_script('meson_post_install.py')