# What To Update

- update these files / replace the `-template` name
  - pyproject.toml
  - CHANGELOG.md
  - readthedocs.yml
  - .python-version
  - .github/workflows/publish-to-pypi.yml
  - .envrc
  - .bumpversion.cfg
  - bibt/template/\* [change name of dir!]
  - docs/modules/template.rst [change name of file!]
  - docs/conf.py
  - docs/index.rst
  - docs/template.rst [change name of file!]

```bash
pyenv virtualenv 3.11.2 bibt-template
pyenv local bibt-template
pip install -r requirements-dev.txt
```

- Create github project

```bash
git init
pre-commit install
git remote add origin git@github-work:broadinstitute/bibt-template.git
git branch -M main
git add . && git commit -m "init commit"
git push -u origin main
```

- Create pypi project
- Add github to pypi project
  - workflow: `publish-to-pypi.yml`
  - env: `publish`
- Create protected branch rule in github
- Create publish environment in github project
- Add protections for publish environment
  - branch: main
  - tags: `v[0-9]*.[0-9]*.[0-9]*`
- Create readthedocs project

```bash
git add && git commit -m "init deploy"
bumpversion patch
git push && git push --tags
```

- remember to add dependencies to BOTH `pyproject.toml` and `requirements.txt`

---

# bibt-template: BITS Blue Team Utilities: Template Module

- **Developer**: Matthew OBrien
- **Email**: mobrien@broadinstitute.org
- **Project URL**: https://pypi.org/project/bibt-template/
- **Project Repo**: https://github.com/broadinstitute/bibt-template
- **Project Documentation**: https://bibt-template.readthedocs.io/en/latest/

## Installing

```bash
$ pip install --upgrade bibt-template
```

## Usage

- See documentation here: https://bibt-template.readthedocs.io/en/latest/
