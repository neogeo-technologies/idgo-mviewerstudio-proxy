import setuptools


setuptools.setup(
    name="mviewerstudio-cas",
    version="0.1.0",
    author="Sébastien DA ROCHA",
    author_email="sebastien@da-rocha.net",
    description="A CAS enabled Proxy for mviewerstudio",
    packages=setuptools.find_packages(where="mviewerstudio_cas/*"),
    classifiers=(
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3 :: Only',
        "Operating System :: OS Independent",
    ),
    install_requires=[
        "Flask>=1.0.0,<1.1.0",
        "Flask-CAS>=1.0.0,<1.1.0",
        "xmltodict>=0.11.0,<0.12.0",
        "requests",
    ],
)

