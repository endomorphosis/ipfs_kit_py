#!/usr/bin/env node

import SynapseWrapper from './synapse_wrapper.js';

async function testWrapper() {
    try {
        console.log('Testing SynapseWrapper...');
        const wrapper = new SynapseWrapper();
        console.log('✓ Wrapper instantiated successfully');
        
        // Test with a simple test method
        console.log('✓ Wrapper is working with ES modules');
        return true;
    } catch (error) {
        console.error('✗ Wrapper test failed:', error.message);
        console.error(error.stack);
        return false;
    }
}

testWrapper().then(success => {
    console.log(`Test result: ${success ? 'PASS' : 'FAIL'}`);
    process.exit(success ? 0 : 1);
});
