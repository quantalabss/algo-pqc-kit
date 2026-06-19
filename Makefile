.PHONY: test build-contracts deploy-localnet

test:
	@echo "Starting LocalNet..."
	algokit localnet start
	@echo "Running tests..."
	pytest tests/ -v
	@echo "Stopping LocalNet..."
	algokit localnet stop

build-contracts:
	@echo "Compiling smart contracts..."
	puyapy --target-avm-version 12 contracts/falcon_vault.py contracts/pqc_dao.py
	@echo "Compilation successful. ARC-56 artifacts generated."

deploy-localnet:
	@echo "Deploying to LocalNet..."
	algokit localnet start
	python scripts/deploy.py --network localnet
