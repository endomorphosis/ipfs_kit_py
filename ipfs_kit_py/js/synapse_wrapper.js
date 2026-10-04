
import { Synapse, RPC_URLS, TOKENS, CONTRACT_ADDRESSES } from '@filoz/synapse-sdk';
import { ethers } from 'ethers';
import { createRequire } from 'module';
const require = createRequire(import.meta.url);

class SynapseWrapper {
    constructor() {
        this.synapse = null;
        this.storage = null;
    }

    async initialize(config) {
        try {
            const options = {
                privateKey: config.privateKey,
                rpcURL: config.rpcUrl || RPC_URLS.calibration.http
            };

            if (config.authorization) {
                options.authorization = config.authorization;
            }

            if (config.pandoraAddress) {
                options.pandoraAddress = config.pandoraAddress;
            }

            this.synapse = await Synapse.create(options);
            return { success: true, network: this.synapse.getNetwork() };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async createStorage(options = {}) {
        try {
            if (!this.synapse) {
                throw new Error('Synapse not initialized');
            }

            this.storage = await this.synapse.createStorage(options);
            return {
                success: true,
                proofSetId: this.storage.proofSetId,
                storageProvider: this.storage.storageProvider
            };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async storeData(data, options = {}) {
        try {
            if (!this.storage) {
                await this.createStorage();
            }

            const dataBuffer = Buffer.from(data, 'base64');
            const result = await this.storage.upload(dataBuffer, options);
            
            return {
                success: true,
                commp: result.commp,
                size: result.size,
                rootId: result.rootId
            };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async retrieveData(commp, options = {}) {
        try {
            if (!this.synapse) {
                throw new Error('Synapse not initialized');
            }

            const data = await this.synapse.download(commp, options);
            return {
                success: true,
                data: Buffer.from(data).toString('base64')
            };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async getBalance(token = 'USDFC') {
        try {
            if (!this.synapse) {
                throw new Error('Synapse not initialized');
            }

            const balance = await this.synapse.payments.balance();
            const walletBalance = await this.synapse.payments.walletBalance(token);
            
            return {
                success: true,
                contractBalance: balance.toString(),
                walletBalance: walletBalance.toString()
            };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async depositFunds(amount, token = 'USDFC') {
        try {
            if (!this.synapse) {
                throw new Error('Synapse not initialized');
            }

            const amountBigInt = ethers.parseUnits(amount, 18);
            const tx = await this.synapse.payments.deposit(amountBigInt, token);
            
            return {
                success: true,
                transactionHash: tx.hash
            };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async approveService(serviceAddress, rateAllowance, lockupAllowance) {
        try {
            if (!this.synapse) {
                throw new Error('Synapse not initialized');
            }

            const rateAmount = ethers.parseUnits(rateAllowance, 18);
            const lockupAmount = ethers.parseUnits(lockupAllowance, 18);
            
            const tx = await this.synapse.payments.approveService(
                serviceAddress,
                rateAmount,
                lockupAmount
            );
            
            return {
                success: true,
                transactionHash: tx.hash
            };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async getStorageInfo() {
        try {
            if (!this.synapse) {
                throw new Error('Synapse not initialized');
            }

            const info = await this.synapse.getStorageInfo();
            return { success: true, info };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async getProviderInfo(providerAddress) {
        try {
            if (!this.synapse) {
                throw new Error('Synapse not initialized');
            }

            const info = await this.synapse.getProviderInfo(providerAddress);
            return { success: true, info };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async getPieceStatus(commp) {
        try {
            if (!this.storage) {
                throw new Error('Storage service not created');
            }

            const status = await this.storage.pieceStatus(commp);
            return { success: true, status };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }
}

// CLI interface for Python integration
const wrapper = new SynapseWrapper();

process.stdin.setEncoding('utf8');
let inputData = '';

process.stdin.on('data', (chunk) => {
    inputData += chunk;
});

process.stdin.on('end', async () => {
    try {
        const command = JSON.parse(inputData);
        let result;
        
        switch (command.method) {
            case 'initialize':
                result = await wrapper.initialize(command.params);
                break;
            case 'createStorage':
                result = await wrapper.createStorage(command.params || {});
                break;
            case 'storeData':
                result = await wrapper.storeData(command.params.data, command.params.options || {});
                break;
            case 'retrieveData':
                result = await wrapper.retrieveData(command.params.commp, command.params.options || {});
                break;
            case 'getBalance':
                result = await wrapper.getBalance(command.params.token);
                break;
            case 'depositFunds':
                result = await wrapper.depositFunds(command.params.amount, command.params.token);
                break;
            case 'approveService':
                result = await wrapper.approveService(
                    command.params.serviceAddress,
                    command.params.rateAllowance,
                    command.params.lockupAllowance
                );
                break;
            case 'getStorageInfo':
                result = await wrapper.getStorageInfo();
                break;
            case 'getProviderInfo':
                result = await wrapper.getProviderInfo(command.params.providerAddress);
                break;
            case 'getPieceStatus':
                result = await wrapper.getPieceStatus(command.params.commp);
                break;
            default:
                result = { success: false, error: 'Unknown method: ' + command.method };
        }
        
        console.log(JSON.stringify(result));
    } catch (error) {
        console.log(JSON.stringify({ success: false, error: error.message }));
    }
});

export default SynapseWrapper;
