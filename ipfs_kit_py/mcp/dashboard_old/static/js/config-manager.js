// Configuration Management Functions
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const data = await response.json();
        const configContent = document.getElementById('config-content');
        configContent.innerHTML = '';

        // Main config section
        if (data.config.main) {
            const mainConfig = `
                <div class="card p-6 mb-8">
                    <h4 class="text-xl font-bold mb-4">Main Configuration</h4>
                    <pre class="bg-gray-100 p-4 rounded-lg text-sm">${JSON.stringify(data.config.main, null, 2)}</pre>
                </div>
            `;
            configContent.innerHTML += mainConfig;
        }

        // Backend config section
        if (data.config.backends) {
            const backendTypesResponse = await fetch('/api/backends/types');
            const backendTypesData = await backendTypesResponse.json();
            const backendTypes = backendTypesData.types;

            let backendHtml = '<div class="card p-6"><h4 class="text-xl font-bold mb-4">Backend Configurations</h4>';
            for (const backendName in data.config.backends) {
                const backend = data.config.backends[backendName];
                const backendType = backend.config.type;
                const typeInfo = backendTypes.find(t => t.name === backendType);

                backendHtml += `
                    <div class="mb-6 p-4 border rounded-lg">
                        <h5 class="text-lg font-semibold">${backendName} <span class="text-sm text-gray-500">(${typeInfo ? typeInfo.display : backendType})</span></h5>
                        <form id="form-${backendName}" onsubmit="updateBackendConfig(event, '${backendName}')">
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                `;

                // Dynamically create form fields based on backend type
                if (backendType === 's3') {
                    backendHtml += createTextField('endpoint', 'Endpoint URL', backend.config.endpoint);
                    backendHtml += createTextField('access_key', 'Access Key', backend.config.access_key);
                    backendHtml += createTextField('secret_key', 'Secret Key', backend.config.secret_key, 'password');
                    backendHtml += createTextField('bucket', 'Bucket Name', backend.config.bucket);
                    backendHtml += createTextField('region', 'Region', backend.config.region);
                } else if (backendType === 'huggingface') {
                    backendHtml += createTextField('token', 'HuggingFace Token', backend.config.token, 'password');
                    backendHtml += createTextField('endpoint', 'Endpoint', backend.config.endpoint);
                } else if (backendType === 'gdrive') {
                    backendHtml += createTextField('credentials_path', 'Credentials Path', backend.config.credentials_path);
                    backendHtml += createTextField('token', 'OAuth Token', backend.config.token, 'password');
                } else if (backendType === 'ipfs') {
                    backendHtml += createTextField('api_url', 'API URL', backend.config.api_url);
                    backendHtml += createTextField('gateway_url', 'Gateway URL', backend.config.gateway_url);
                }

                backendHtml += `
                            </div>
                            <div class="mt-4 flex justify-end">
                                <button type="submit" class="btn-primary px-4 py-2 rounded-lg">Save Changes</button>
                            </div>
                        </form>
                    </div>
                `;
            }
            backendHtml += '</div>';
            configContent.innerHTML += backendHtml;
        }

    } catch (error) {
        console.error('Error loading config:', error);
        document.getElementById('config-content').innerHTML = '<p class="text-red-500">Failed to load configuration.</p>';
    }
}

function createTextField(id, label, value, type = 'text') {
    return `
        <div class="mb-4">
            <label for="${id}" class="block text-sm font-medium text-gray-700">${label}</label>
            <input type="${type}" id="${id}" name="${id}" value="${value || ''}" class="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm">
        </div>
    `;
}

async function updateBackendConfig(event, backendName) {
    event.preventDefault();
    const form = document.getElementById(`form-${backendName}`);
    const formData = new FormData(form);
    const config = {};
    for (const [key, value] of formData.entries()) {
        config[key] = value;
    }

    try {
        const response = await fetch(`/api/config/backends/${backendName}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ config }),
        });
        const result = await response.json();
        if (result.success) {
            alert('Configuration updated successfully!');
            loadConfig(); // Refresh the config tab
        } else {
            alert(`Error updating configuration: ${result.error}`);
        }
    } catch (error) {
        console.error('Error updating config:', error);
        alert('An unexpected error occurred.');
    }
}
