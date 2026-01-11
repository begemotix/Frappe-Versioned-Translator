from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
	long_description = f.read()

setup(
	name="versioned_translator",
	version="0.0.1",
	description="Frappe App for Versioned Translations",
	author="Your Name",
	author_email="your.email@example.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=[
		"requests>=2.28.0",
	],
)
