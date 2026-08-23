# branch-as-code — convenience targets. `make help` lists them.

CLAB     = sudo containerlab
CLAB_TOPO = containerlab/branch-001.clab.yml
ANSIBLE  = cd ansible && ansible-playbook

.PHONY: help render render-netbox lab-up lab-down redeploy deploy verify netbox-up populate

help:
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

render: ## Render configs from the static YAML SoT
	$(ANSIBLE) render.yml

render-netbox: ## Render configs from NetBox (NETBOX_URL/TOKEN env)
	$(ANSIBLE) -i inventories/netbox.yml render.yml

lab-up: ## Deploy the containerlab topology
	$(CLAB) deploy -t $(CLAB_TOPO)

lab-down: ## Destroy the lab
	$(CLAB) destroy -t $(CLAB_TOPO) --cleanup

redeploy: ## Rebuild nodes (picks up bind-mounted config changes)
	$(CLAB) redeploy -t $(CLAB_TOPO)

deploy: ## Push rendered configs to running nodes
	$(ANSIBLE) deploy.yml

verify: ## Run post-change verification
	$(ANSIBLE) verify.yml

netbox-up: ## Start NetBox (expects netbox-docker clone in ../netbox-docker)
	cd ../netbox-docker && docker compose up -d

populate: ## Populate NetBox with the branch-001 data model
	python3 scripts/netbox_populate.py
