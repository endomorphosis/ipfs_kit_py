// Pins Management Functions
async function loadPins() {
    try {
        const response = await fetch('/api/pins');
        const data = await response.json();
        const pinsList = document.getElementById('pins-list');
        pinsList.innerHTML = ''; // Clear existing list

        if (data.pins && data.pins.length > 0) {
            data.pins.forEach(pin => {
                const row = `
                    <tr class="hover:bg-gray-50">
                        <td class="p-4 text-sm text-gray-800 font-mono">${pin.cid}</td>
                        <td class="p-4 text-sm text-gray-600">${pin.name || ''}</td>
                        <td class="p-4 text-right">
                            <button onclick="removePin('${pin.cid}')" class="text-red-500 hover:text-red-700 font-semibold">
                                <i class="fas fa-trash-alt mr-1"></i> Remove
                            </button>
                        </td>
                    </tr>
                `;
                pinsList.innerHTML += row;
            });
        } else {
            pinsList.innerHTML = '<tr><td colspan="3" class="p-8 text-center text-gray-500">No pins found.</td></tr>';
        }
    } catch (error) {
        console.error('Error loading pins:', error);
        const pinsList = document.getElementById('pins-list');
        pinsList.innerHTML = '<tr><td colspan="3" class="p-8 text-center text-red-500">Failed to load pins.</td></tr>';
    }
}

async function addPin() {
    const cid = document.getElementById('pin-cid-input').value;
    const name = document.getElementById('pin-name-input').value;

    if (!cid) {
        alert('Please enter a CID.');
        return;
    }

    try {
        const response = await fetch('/api/pins', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cid, name }),
        });
        const result = await response.json();
        if (result.success) {
            document.getElementById('pin-cid-input').value = '';
            document.getElementById('pin-name-input').value = '';
            loadPins(); // Refresh the list
        } else {
            alert(`Error adding pin: ${result.error}`);
        }
    } catch (error) {
        console.error('Error adding pin:', error);
        alert('An unexpected error occurred while adding the pin.');
    }
}

async function removePin(cid) {
    if (!confirm(`Are you sure you want to remove pin ${cid}?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/pins/${cid}`, {
            method: 'DELETE',
        });
        const result = await response.json();
        if (result.success) {
            loadPins(); // Refresh the list
        } else {
            alert(`Error removing pin: ${result.error}`);
        }
    } catch (error) {
        console.error('Error removing pin:', error);
        alert('An unexpected error occurred while removing the pin.');
    }
}
