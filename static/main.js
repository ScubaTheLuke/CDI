(function () {
    const body = document.body;
    const themeToggle = document.getElementById('theme-toggle-input');
    const storedTheme = localStorage.getItem('cdi-theme');
    if (storedTheme === 'classic') {
        body.classList.add('classic-mode');
        if (themeToggle) {
            themeToggle.checked = true;
        }
    }
    if (themeToggle) {
        themeToggle.addEventListener('change', () => {
            if (themeToggle.checked) {
                body.classList.add('classic-mode');
                localStorage.setItem('cdi-theme', 'classic');
            } else {
                body.classList.remove('classic-mode');
                localStorage.setItem('cdi-theme', 'dark');
            }
            updateSetSymbolFilters();
        });
    }

    function updateSetSymbolFilters() {
        const symbols = document.querySelectorAll('[data-set-symbol]');
        symbols.forEach((symbol) => {
            if (body.classList.contains('classic-mode')) {
                symbol.classList.remove('invert');
            } else {
                symbol.classList.add('invert');
            }
        });
    }

    const tabButtons = document.querySelectorAll('.tab-button');
    const sections = document.querySelectorAll('.tab-section');

    function activateTab(id) {
        tabButtons.forEach((button) => {
            button.classList.toggle('active', button.dataset.target === id);
        });
        sections.forEach((section) => {
            section.classList.toggle('active', section.id === id);
        });
        if (history.replaceState) {
            history.replaceState(null, '', `#${id}`);
        }
    }

    tabButtons.forEach((button) => {
        button.addEventListener('click', () => activateTab(button.dataset.target));
    });

    if (location.hash) {
        const target = location.hash.replace('#', '');
        if (document.getElementById(target)) {
            activateTab(target);
        }
    }

    const cardFilterInput = document.getElementById('card-filter');
    if (cardFilterInput) {
        cardFilterInput.addEventListener('input', () => {
            const term = cardFilterInput.value.trim().toLowerCase();
            document.querySelectorAll('#cards-table tbody tr').forEach((row) => {
                const haystack = [
                    row.dataset.name || '',
                    row.dataset.set || '',
                    row.dataset.notes || ''
                ].join(' ');
                row.classList.toggle('hidden', term && !haystack.includes(term));
            });
        });
    }

    function attachSelectAll(masterId, selector) {
        const master = document.getElementById(masterId);
        if (!master) return;
        master.addEventListener('change', () => {
            document.querySelectorAll(selector).forEach((checkbox) => {
                checkbox.checked = master.checked;
            });
        });
    }

    attachSelectAll('card-select-all', '.card-select');
    attachSelectAll('sealed-select-all', '.sealed-select');

    const modalOverlay = document.getElementById('modal-overlay');
    const modalForm = document.getElementById('modal-form');
    const modalCancel = document.getElementById('modal-cancel');
    const modalTitle = document.getElementById('modal-title');
    let modalContext = null;

    function openModal(context) {
        modalContext = context;
        if (modalTitle) {
            modalTitle.textContent = context === 'cards' ? 'Mass Update Cards' : 'Mass Update Sealed Products';
        }
        modalForm.reset();
        modalOverlay.classList.remove('hidden');
    }

    function closeModal() {
        modalOverlay.classList.add('hidden');
        modalContext = null;
    }

    const cardMassButton = document.getElementById('card-mass-edit');
    if (cardMassButton) {
        cardMassButton.addEventListener('click', () => openModal('cards'));
    }
    const sealedMassButton = document.getElementById('sealed-mass-edit');
    if (sealedMassButton) {
        sealedMassButton.addEventListener('click', () => openModal('sealed'));
    }

    if (modalCancel) {
        modalCancel.addEventListener('click', closeModal);
    }

    if (modalOverlay) {
        modalOverlay.addEventListener('click', (event) => {
            if (event.target === modalOverlay) {
                closeModal();
            }
        });
    }

    if (modalForm) {
        modalForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            if (!modalContext) return;
            const formData = new FormData(modalForm);
            const payload = {};
            formData.forEach((value, key) => {
                if (value !== null && value !== '') {
                    payload[key] = value;
                }
            });
            if (!Object.keys(payload).length) {
                alert('Enter at least one field to update.');
                return;
            }
            const selection = Array.from(document.querySelectorAll(modalContext === 'cards' ? '.card-select:checked' : '.sealed-select:checked'));
            if (!selection.length) {
                alert('Select at least one inventory item to update.');
                return;
            }
            const items = selection.map((checkbox) => ({ id: Number(checkbox.value), ...payload }));
            const endpoint = modalContext === 'cards' ? '/inventory/cards/bulk-update' : '/inventory/sealed/bulk-update';
            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(items)
                });
                if (!response.ok) {
                    const error = await response.json().catch(() => ({ error: 'Update failed' }));
                    alert(error.error || 'Update failed');
                    return;
                }
                location.reload();
            } catch (error) {
                alert('Unable to complete update.');
            }
        });
    }

    const scryfallButton = document.getElementById('scryfall-search');
    if (scryfallButton) {
        scryfallButton.addEventListener('click', async () => {
            const nameInput = document.getElementById('card-name');
            const setInput = document.getElementById('card-set');
            if (!nameInput || !nameInput.value.trim()) {
                alert('Enter a card name before searching.');
                return;
            }
            const name = nameInput.value.trim();
            const setCode = setInput && setInput.value.trim();
            let query = `!"${name}"`;
            if (setCode) {
                query += ` set:${setCode}`;
            }
            try {
                const response = await fetch(`/api/scryfall/search?query=${encodeURIComponent(query)}`);
                if (!response.ok) {
                    throw new Error('Lookup failed');
                }
                const payload = await response.json();
                const card = payload.data && payload.data.length ? payload.data[0] : null;
                if (!card) {
                    alert('No results from Scryfall.');
                    return;
                }
                document.getElementById('card-scryfall-id').value = card.id || '';
                if (card.set_code && setInput && !setInput.value) {
                    setInput.value = card.set_code;
                }
                const collectorNumber = document.getElementById('collector-number');
                if (collectorNumber && card.collector_number && !collectorNumber.value) {
                    collectorNumber.value = card.collector_number;
                }
                const priceInput = document.getElementById('card-market');
                if (priceInput && card.prices && card.prices.usd) {
                    priceInput.value = card.prices.usd;
                }
                alert('Scryfall data applied.');
            } catch (error) {
                alert('Unable to reach Scryfall.');
            }
        });
    }

    const saleItemSelect = document.getElementById('sale-item-select');
    const saleSupplySelect = document.getElementById('sale-supply-select');

    function populateSaleSelects() {
        if (saleItemSelect) {
            saleItemSelect.innerHTML = '';
            const defaultOption = document.createElement('option');
            defaultOption.value = '';
            defaultOption.textContent = 'Select inventory item';
            saleItemSelect.appendChild(defaultOption);
            const cardGroup = document.createElement('optgroup');
            cardGroup.label = 'Single Cards';
            (inventoryData.cards || []).forEach((card) => {
                const option = document.createElement('option');
                option.value = `${card.id}`;
                option.textContent = `${card.name} (${card.set_code || 'N/A'}) x${card.quantity}`;
                option.dataset.type = 'single';
                option.dataset.market = card.market_price;
                cardGroup.appendChild(option);
            });
            const sealedGroup = document.createElement('optgroup');
            sealedGroup.label = 'Sealed Products';
            (inventoryData.sealed || []).forEach((product) => {
                const option = document.createElement('option');
                option.value = `${product.id}`;
                option.textContent = `${product.name} (${product.set_code || 'N/A'}) x${product.quantity}`;
                option.dataset.type = 'sealed';
                option.dataset.market = product.market_price;
                sealedGroup.appendChild(option);
            });
            saleItemSelect.appendChild(cardGroup);
            saleItemSelect.appendChild(sealedGroup);
        }
        if (saleSupplySelect) {
            saleSupplySelect.innerHTML = '';
            const defaultOption = document.createElement('option');
            defaultOption.value = '';
            defaultOption.textContent = 'Select supply batch';
            saleSupplySelect.appendChild(defaultOption);
            (inventoryData.supplies || []).forEach((supply) => {
                const option = document.createElement('option');
                option.value = `${supply.id}`;
                option.textContent = `${supply.description} (available ${supply.quantity_available})`;
                saleSupplySelect.appendChild(option);
            });
        }
    }

    populateSaleSelects();

    const saleItemsTable = document.getElementById('sale-items-table');
    const saleSuppliesTable = document.getElementById('sale-supplies-table');

    function addSaleItemRow(item) {
        if (!saleItemsTable) return;
        const row = document.createElement('tr');
        row.dataset.payload = JSON.stringify(item);
        row.innerHTML = `
            <td>${item.name}</td>
            <td>${item.inventory_type}</td>
            <td>${item.quantity}</td>
            <td>$${Number(item.sale_price_per_unit).toFixed(2)}</td>
            <td><button type="button" class="link">Remove</button></td>
        `;
        saleItemsTable.querySelector('tbody').appendChild(row);
    }

    function addSaleSupplyRow(item) {
        if (!saleSuppliesTable) return;
        const row = document.createElement('tr');
        row.dataset.payload = JSON.stringify(item);
        row.innerHTML = `
            <td>${item.description}</td>
            <td>${item.quantity_used}</td>
            <td><button type="button" class="link">Remove</button></td>
        `;
        saleSuppliesTable.querySelector('tbody').appendChild(row);
    }

    if (saleItemsTable) {
        saleItemsTable.addEventListener('click', (event) => {
            if (event.target instanceof HTMLElement && event.target.matches('button.link')) {
                event.target.closest('tr')?.remove();
            }
        });
    }

    if (saleSuppliesTable) {
        saleSuppliesTable.addEventListener('click', (event) => {
            if (event.target instanceof HTMLElement && event.target.matches('button.link')) {
                event.target.closest('tr')?.remove();
            }
        });
    }

    const saleQuantityInput = document.getElementById('sale-item-quantity');
    const salePriceInput = document.getElementById('sale-item-price');

    const addSaleItemButton = document.getElementById('add-sale-item');
    if (addSaleItemButton) {
        addSaleItemButton.addEventListener('click', () => {
            if (!saleItemSelect || !saleItemSelect.value) {
                alert('Choose an inventory item.');
                return;
            }
            const option = saleItemSelect.options[saleItemSelect.selectedIndex];
            const quantity = Number(saleQuantityInput.value || 0);
            const salePrice = Number(salePriceInput.value || 0);
            if (!quantity || !salePrice) {
                alert('Enter quantity and sale price.');
                return;
            }
            const item = {
                inventory_type: option.dataset.type,
                inventory_id: Number(option.value),
                name: option.textContent,
                quantity,
                sale_price_per_unit: salePrice,
            };
            addSaleItemRow(item);
            saleQuantityInput.value = '1';
            salePriceInput.value = option.dataset.market || '';
        });
    }

    const addSaleSupplyButton = document.getElementById('add-sale-supply');
    if (addSaleSupplyButton) {
        addSaleSupplyButton.addEventListener('click', () => {
            if (!saleSupplySelect || !saleSupplySelect.value) {
                alert('Choose a supply batch.');
                return;
            }
            const quantity = Number(document.getElementById('sale-supply-quantity').value || 0);
            if (!quantity) {
                alert('Enter a quantity for supplies.');
                return;
            }
            const option = saleSupplySelect.options[saleSupplySelect.selectedIndex];
            const item = {
                supply_batch_id: Number(option.value),
                description: option.textContent,
                quantity_used: quantity,
            };
            addSaleSupplyRow(item);
            document.getElementById('sale-supply-quantity').value = '1';
        });
    }

    const saleForm = document.getElementById('sale-form');
    if (saleForm) {
        saleForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            if (!saleItemsTable || !saleSuppliesTable) {
                return;
            }
            const itemRows = Array.from(saleItemsTable.querySelectorAll('tbody tr'));
            if (!itemRows.length) {
                alert('Add at least one sale item.');
                return;
            }
            const salePayload = {
                sale_date: saleForm.sale_date.value || null,
                platform: saleForm.platform.value || null,
                customer_shipping_charged: saleForm.customer_shipping_charged.value || 0,
                actual_postage_cost: saleForm.actual_postage_cost.value || 0,
                platform_fees: saleForm.platform_fees.value || 0,
                notes: saleForm.notes.value || null,
                items: itemRows.map((row) => JSON.parse(row.dataset.payload)),
                supplies: Array.from(saleSuppliesTable.querySelectorAll('tbody tr')).map((row) => JSON.parse(row.dataset.payload)),
            };
            try {
                const response = await fetch('/sales/record', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(salePayload)
                });
                if (!response.ok) {
                    const error = await response.json().catch(() => ({ error: 'Unable to record sale' }));
                    alert(error.error || 'Unable to record sale');
                    return;
                }
                location.reload();
            } catch (error) {
                alert('Failed to record sale.');
            }
        });
    }

    document.querySelectorAll('[data-set-symbol]').forEach((symbol) => {
        symbol.classList.toggle('invert', !body.classList.contains('classic-mode'));
    });
})();
