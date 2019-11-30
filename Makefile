# You can set these variables from the command line, and also from the environment for the first two.
SOURCEDIR     = source
BUILDDIR      = build
TESTDIR       = munggoggo/tests
MAKEFILE_LIST = /tmp/makefile_list.txt
MAKE          = make

.PHONY: all help docs clean

# Put it first so that "make" without argument is like "make help".
help:
	@echo "$(MAKE) [all,docs,clean,bump,release,frontend]"

default: all

#all: unit
all: check clean docs bump
	@echo "--------------------------------------------------------------------------------"
	@echo "-M- commit changes"
	@echo "-M- use <bump!> to confirm"
	@echo "-M- commit amend README.rst"
	@echo "-M- use <release> to switch to 'prod'"
	@echo "--------------------------------------------------------------------------------"
	@git add .
	@git status

unit:
	py.test "$(TESTDIR)"

docs:
	#rm -rf docs/build/
	make -C docs/ clean
	make -C docs/ html
	cp docs/source/index.rst README.rst

clean:
	@echo "Cleaning up..."
	#git clean -Xdf
	rm -rf docs/build
	rm -rf static/*

bump: check
	@echo "Bumping part: $(part)"
	bump2version --dry-run --allow-dirty --verbose $(part)
	@echo "use <bump!> to confirm"

bump!: check
	cp docs/source/index.rst README.rst  # changed by bump2version
	git add README.rst
	bump2version --allow-dirty --verbose $(part)
	@echo "use release after bump"

release:
	bump2version --allow-dirty --verbose release

check:
	@[ "${part}" ] || ( echo "-E- bump2version <part> is not set"; exit 1 )

frontend: check
	@echo "building and installing frontend"
	./scripts/install_frontend.sh build
	./scripts/install_frontend.sh install
