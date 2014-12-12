from disturils.core import setup

setup(
    name = "bocado",
    version = "0.1",
    author = "Emma Tosch",
    author_email = "etosch@cs.umass.edu",
    packages = ["bocado"],
    package_dir={"src/bocado"}
    package_data = {"": ["schemata/*", "protos/*"]},
    licence = "Apache 2.0"
)
