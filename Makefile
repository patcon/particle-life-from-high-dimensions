serve: ## Serve HTML files via local Python HTTP server
	python3 -m http.server 8000

# These make tasks allow the default help text to work properly.
%:
	@true

.PHONY: help serve

help:
	@echo 'Usage: make <command>'
	@echo
	@echo 'where <command> is one of the following:'
	@echo
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
