#
# Main Makefile for project development and CI
#

# Default shell
SHELL := /bin/bash
# Fail on first error
.SHELLFLAGS := -ec

# Global variables
LIB_DIR := ./
LIB_NAME := filzl

CREATE_FILZL_APP_DIR := create_filzl_app
CREATE_FILZL_APP_NAME := create_filzl_app

MY_WEBSITE_DIR := my_website
MY_WEBSITE_NAME := my_website

PLUGIN_FIZL_AUTH_DIR := filzl-plugins/filzl-auth
PLUGIN_FIZL_AUTH_NAME := filzl_auth

PLUGIN_FIZL_DAEMONS_DIR := filzl-plugins/filzl-daemons
PLUGIN_FIZL_DAEMONS_NAME := filzl_daemons

# Ignore these directories in the local filesystem if they exist
.PHONY: lint test

# Main lint target
lint: lint-lib lint-create-filzl-app lint-my-website lint-plugins

# Lint validation target
lint-validation: lint-validation-lib lint-validation-create-filzl-app lint-validation-my-website lint-validation-plugins

# Testing target
test: test-lib test-create-filzl-app test-plugin-auth test-plugin-daemons

# Integration testing target
test-integrations: test-create-filzl-app-integrations

# Install all sub-project dependencies with poetry
install-deps:
	@echo "Installing dependencies for $(LIB_DIR)..."
	@(cd $(LIB_DIR) && poetry install)
	@(cd $(LIB_DIR) && poetry run maturin develop --release)

	@echo "Installing dependencies for $(CREATE_FILZL_APP_DIR)..."
	@(cd $(CREATE_FILZL_APP_DIR) && poetry install)

	@echo "Installing dependencies for $(MY_WEBSITE_DIR)..."
	@(cd $(MY_WEBSITE_DIR) && poetry install)

	@echo "Installing dependencies for $(PLUGIN_FIZL_AUTH_DIR)..."
	@(cd $(PLUGIN_FIZL_AUTH_DIR) && poetry install)

	@echo "Installing dependencies for $(PLUGIN_FIZL_DAEMONS_DIR)..."
	@(cd $(PLUGIN_FIZL_DAEMONS_DIR) && poetry install)
	@(cd $(PLUGIN_FIZL_DAEMONS_DIR) && poetry run maturin develop --release)

# Clean the current poetry.lock files, useful for remote CI machines
# where we're running on a different base architecture than when
# developing locally
clean-poetry-lock:
	@echo "Cleaning poetry.lock files..."
	@rm -f $(LIB_DIR)/poetry.lock
	@rm -f $(CREATE_FILZL_APP_DIR)/poetry.lock
	@rm -f $(MY_WEBSITE_DIR)/poetry.lock

# Standard linting - local development, with fixing enabled
lint-lib:
	$(call lint-common,$(LIB_DIR),$(LIB_NAME))
lint-create-filzl-app:
	$(call lint-common,$(CREATE_FILZL_APP_DIR),$(CREATE_FILZL_APP_NAME))
lint-my-website:
	$(call lint-common,$(MY_WEBSITE_DIR),$(MY_WEBSITE_NAME))
lint-plugins:
	$(call lint-common,$(PLUGIN_FIZL_AUTH_DIR),$(PLUGIN_FIZL_AUTH_NAME))
	$(call lint-common,$(PLUGIN_FIZL_DAEMONS_DIR),$(PLUGIN_FIZL_DAEMONS_NAME))

# Lint validation - CI to fail on any errors
lint-validation-lib:
	$(call lint-validation-common,$(LIB_DIR),$(LIB_NAME))
lint-validation-create-filzl-app:
	$(call lint-validation-common,$(CREATE_FILZL_APP_DIR),$(CREATE_FILZL_APP_NAME))
lint-validation-my-website:
	$(call lint-validation-common,$(MY_WEBSITE_DIR),$(MY_WEBSITE_NAME))
lint-validation-plugins:
	$(call lint-validation-common,$(PLUGIN_FIZL_AUTH_DIR),$(PLUGIN_FIZL_AUTH_NAME))
	$(call lint-validation-common,$(PLUGIN_FIZL_DAEMONS_DIR),$(PLUGIN_FIZL_DAEMONS_NAME))

# Tests
test-lib:
	$(call test-common,$(LIB_DIR),$(LIB_NAME))
	$(call test-rust-common,$(LIB_DIR),$(LIB_NAME))
test-create-filzl-app:
	$(call test-common,$(CREATE_FILZL_APP_DIR),$(CREATE_FILZL_APP_NAME))
test-create-filzl-app-integrations:
	$(call test-common-integrations,$(CREATE_FILZL_APP_DIR),$(CREATE_FILZL_APP_NAME))
test-plugin-auth:
	$(call test-common,$(PLUGIN_FIZL_AUTH_DIR),$(PLUGIN_FIZL_AUTH_NAME))
test-plugin-daemons:
	(cd $(PLUGIN_FIZL_DAEMONS_DIR) && docker-compose up -d)
	@$(call wait-for-postgres,30,5434)
	@set -e; \
	$(call test-common,$(PLUGIN_FIZL_DAEMONS_DIR),$(PLUGIN_FIZL_DAEMONS_NAME)) ;\
	$(call test-rust-common,$(PLUGIN_FIZL_DAEMONS_DIR),$(PLUGIN_FIZL_DAEMONS_NAME)) ;\
	(cd $(PLUGIN_FIZL_DAEMONS_DIR) && docker-compose down)

#
# Common helper functions
#

define test-common
	echo "Running tests for $(2)..."
	@(cd $(1) && poetry run pytest -W error $(2))
endef

define test-rust-common
	echo "Running rust tests for $(2)..."
	@(cd $(1) && cargo test --all)
endef

# Use `-n auto` to run tests in parallel
define test-common-integrations
	echo "Running tests for $(2)..."
	@(cd $(1) && poetry run pytest -s -m integration_tests -W error $(2))
endef

define lint-common
	echo "Running linting for $(2)..."
	@(cd $(1) && poetry run ruff format $(2))
	@(cd $(1) && poetry run ruff check --fix $(2))
	@(cd $(1) && poetry run mypy $(2))
endef

define lint-validation-common
	echo "Running lint validation for $(2)..."
	@(cd $(1) && poetry run ruff format --check $(2))
	@(cd $(1) && poetry run ruff check $(2))
	@(cd $(1) && poetry run mypy $(2))
endef

# Function to wait for PostgreSQL to be ready
define wait-for-postgres
	@echo "Waiting for PostgreSQL to be ready..."
	@timeout=$(1); \
	while ! nc -z localhost $(2) >/dev/null 2>&1; do \
		timeout=$$((timeout-1)); \
		if [ $$timeout -le 0 ]; then \
			echo "Timed out waiting for PostgreSQL to start on port $(2)"; \
			exit 1; \
		fi; \
		echo "Waiting for PostgreSQL to start..."; \
		sleep 1; \
	done; \
	echo "PostgreSQL is ready on port $(2)."
endef
