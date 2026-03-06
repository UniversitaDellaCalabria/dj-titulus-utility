from setuptools import setup, find_packages

setup(
    name="django-titulus-utility",
    version="0.1.0",
    packages=find_packages(include=['titulus_utility', 'titulus_utility.*']),

    include_package_data=True,  # Dice a setuptools di leggere il file MANIFEST.in

    # Metadati opzionali ma consigliati
    description="Utility app for Titulus",
    author="Elena Mastria",
    author_email="elena.mastria@unical.it",

    install_requires=[
        "Django>=6.0.2",
        "Jinja2>=3.0.0",
        "python-magic>=0.4.27",
        "requests>=2.32.0",
        "zeep>=4.3.0",
    ],
)