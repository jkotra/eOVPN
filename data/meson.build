app_resources = gnome.compile_resources(project_id,
    'eovpn.gresource.xml',
    gresource_bundle: true,
    install: true,
    install_dir: pkg_datadir
)


install_data(
    'icons/'+project_id+'.svg',
    install_dir: join_paths(icondir, 'scalable/apps')
)
