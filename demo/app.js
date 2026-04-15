// ── Estado de mutaciones ──────────────────────────────────────────────────────
const originalState = {
  'btn-login':          { id: 'btn-login',          className: 'btn btn-primary',   text: 'Iniciar sesión' },
  'btn-clear':          { id: 'btn-clear',          className: 'btn btn-secondary', text: 'Limpiar'        },
  'input-username':     { id: 'input-username',     className: 'form-input'                                },
  'input-password':     { id: 'input-password',     className: 'form-input'                                },
  'btn-open-confirm':   { id: 'btn-open-confirm',   className: 'btn btn-primary',   text: 'Abrir Confirmación' },
  'btn-open-alert':     { id: 'btn-open-alert',     className: 'btn btn-warning',   text: 'Abrir Alerta'  },
  'btn-add-row':        { id: 'btn-add-row',        className: 'btn btn-primary',   text: '+ Agregar Fila'},
  'btn-delayed-action': { id: 'btn-delayed-action', className: 'btn btn-primary',   text: 'Acción disponible'},
};

let mutationHistory = [];
let rowCounter = 4;

// ── Mutación 1: Cambiar IDs ───────────────────────────────────────────────────
function mutateIds() {
  const mutations = [
    { old: 'btn-login',      new: 'submit-login-btn'    },
    { old: 'btn-clear',      new: 'clear-form-button'   },
    { old: 'input-username', new: 'user-field'           },
    { old: 'input-password', new: 'pass-field'           },
    { old: 'btn-add-row',    new: 'add-new-row-btn'      },
  ];

  mutations.forEach(m => {
    const el = document.getElementById(m.old);
    if (el) {
      el.id = m.new;
      log(`ID: #${m.old} → #${m.new}`);
    }
  });
}

// ── Mutación 2: Cambiar clases CSS ───────────────────────────────────────────
function mutateClasses() {
  const mutations = [
    { id: 'btn-login',        newClass: 'btn btn-success btn-large'    },
    { id: 'btn-open-confirm', newClass: 'btn btn-primary rounded-full' },
    { id: 'btn-open-alert',   newClass: 'btn btn-danger alert-trigger' },
  ];

  mutations.forEach(m => {
    const el = document.getElementById(m.id);
    if (el) {
      const old = el.className;
      el.className = m.newClass;
      log(`Class: #${m.id} → "${m.newClass}"`);
    }
  });
}

// ── Mutación 3: Cambiar textos de botones ─────────────────────────────────────
function mutateText() {
  const mutations = [
    { id: 'btn-login',        text: 'Acceder al sistema' },
    { id: 'btn-clear',        text: 'Borrar campos'      },
    { id: 'btn-open-confirm', text: 'Confirmar acción'   },
    { id: 'btn-add-row',      text: 'Nueva entrada'      },
  ];

  mutations.forEach(m => {
    const el = document.getElementById(m.id);
    if (el) {
      el.textContent = m.text;
      log(`Text: #${m.id} → "${m.text}"`);
    }
  });
}

// ── Reset ─────────────────────────────────────────────────────────────────────
function resetAll() {
  // Restaura todos los elementos a su estado original
  // Primero reconstruye el form para restaurar IDs que cambiaron
  const form = document.getElementById('login-form') ||
               document.querySelector('form#login-form');

  // Restaura IDs directamente buscando por contenido o por nuevos IDs
  const idMap = {
    'submit-login-btn':   'btn-login',
    'clear-form-button':  'btn-clear',
    'user-field':         'input-username',
    'pass-field':         'input-password',
    'add-new-row-btn':    'btn-add-row',
  };

  Object.entries(idMap).forEach(([newId, oldId]) => {
    const el = document.getElementById(newId);
    if (el) el.id = oldId;
  });

  // Restaura clases y textos
  Object.entries(originalState).forEach(([id, state]) => {
    const el = document.getElementById(id);
    if (!el) return;
    if (state.className) el.className = state.className;
    if (state.text)      el.textContent = state.text;
  });

  mutationHistory = [];
  document.getElementById('log-content').innerHTML = 'Reseteo completo ✓';
  document.getElementById('login-result').classList.add('hidden');

  // Oculta el elemento dinámico
  document.getElementById('delayed-element').classList.add('hidden');
  document.getElementById('loading-indicator').classList.add('hidden');

  log('Todo restaurado al estado original');
}

// ── Login ─────────────────────────────────────────────────────────────────────
function handleLogin(event) {
  event.preventDefault();
  const username = document.getElementById('input-username') ||
                   document.getElementById('user-field');
  const password = document.getElementById('input-password') ||
                   document.getElementById('pass-field');
  const result   = document.getElementById('login-result');

  if (!username || !password) {
    showResult(result, 'error', '✗ No se encontraron los campos del formulario');
    return false;
  }

  if (username.value && password.value) {
    showResult(result, 'success',
      `✓ Login exitoso — Bienvenido, ${username.value}`);
  } else {
    showResult(result, 'error', '✗ Ingresa usuario y contraseña');
  }
  return false;
}

function clearForm() {
  ['input-username', 'input-password', 'user-field', 'pass-field'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  document.getElementById('login-result').classList.add('hidden');
}

// ── Modals ────────────────────────────────────────────────────────────────────
const modalTemplates = {
  confirm: `
    <h3>&#10067; Confirmar acción</h3>
    <p>¿Estás seguro de que deseas continuar con esta operación?
       Esta acción no se puede deshacer.</p>
    <div class="modal-actions">
      <button id="btn-modal-confirm" class="btn btn-primary"  onclick="modalAction('confirmed')">Confirmar</button>
      <button id="btn-modal-cancel"  class="btn btn-secondary" onclick="closeModal()">Cancelar</button>
    </div>`,

  alert: `
    <h3>&#9888; Alerta del sistema</h3>
    <p>Se detectó un problema en el módulo de pagos.
       El equipo técnico ha sido notificado automáticamente.</p>
    <div class="modal-actions">
      <button id="btn-modal-accept" class="btn btn-danger" onclick="modalAction('accepted')">Entendido</button>
    </div>`,

  form: `
    <h3>&#128221; Nuevo registro</h3>
    <div class="form-group" style="margin-bottom:12px">
      <label style="color:#94a3b8;font-size:.85rem">Nombre</label>
      <input type="text" id="modal-input-name" class="form-input" placeholder="Nombre completo"/>
    </div>
    <div class="form-group">
      <label style="color:#94a3b8;font-size:.85rem">Estado</label>
      <select id="modal-select-status" class="form-input">
        <option value="active">Activo</option>
        <option value="inactive">Inactivo</option>
        <option value="pending">Pendiente</option>
      </select>
    </div>
    <div class="modal-actions">
      <button id="btn-modal-save"   class="btn btn-primary"   onclick="saveModalForm()">Guardar</button>
      <button id="btn-modal-cancel" class="btn btn-secondary" onclick="closeModal()">Cancelar</button>
    </div>`,
};

function openModal(type) {
  document.getElementById('modal-content').innerHTML = modalTemplates[type];
  document.getElementById('modal-overlay').classList.remove('hidden');
}

function closeModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
}

function modalAction(action) {
  closeModal();
  log(`Modal: acción "${action}" ejecutada`);
}

function saveModalForm() {
  const name   = document.getElementById('modal-input-name').value;
  const status = document.getElementById('modal-select-status').value;
  if (name) {
    addRowWithData(name, status);
    log(`Modal form: guardado "${name}" (${status})`);
  }
  closeModal();
}

// ── Tabla dinámica ────────────────────────────────────────────────────────────
function addRow() {
  const names = ['Ana Torres','Luis Rodríguez','Sofia Martínez',
                 'Pedro Jiménez','Laura Sánchez','Diego Ramírez'];
  const name = names[Math.floor(Math.random() * names.length)];
  addRowWithData(name, Math.random() > 0.3 ? 'active' : 'pending');
}

function addRowWithData(name, status) {
  const tbody = document.getElementById('table-body');
  const id = String(rowCounter++).padStart(3, '0');
  const badgeClass = status === 'active'   ? 'badge-active'   :
                     status === 'inactive' ? 'badge-inactive' : 'badge-pending';
  const badgeText  = status === 'active'   ? 'Activo'         :
                     status === 'inactive' ? 'Inactivo'       : 'Pendiente';

  const tr = document.createElement('tr');
  tr.dataset.id = rowCounter - 1;
  tr.innerHTML = `
    <td>${id}</td>
    <td>${name}</td>
    <td><span class="badge ${badgeClass}">${badgeText}</span></td>
    <td><button class="btn-action" onclick="editRow(this)">Editar</button></td>`;
  tbody.appendChild(tr);
  log(`Tabla: fila agregada — ${name}`);
}

function removeRow() {
  const tbody = document.getElementById('table-body');
  if (tbody.lastElementChild) {
    const name = tbody.lastElementChild.cells[1].textContent;
    tbody.removeChild(tbody.lastElementChild);
    log(`Tabla: última fila eliminada (${name})`);
  }
}

function sortRows() {
  const tbody = document.getElementById('table-body');
  const rows  = Array.from(tbody.querySelectorAll('tr'));
  rows.sort((a, b) => a.cells[1].textContent.localeCompare(b.cells[1].textContent));
  rows.forEach(r => tbody.appendChild(r));
  log('Tabla: filas ordenadas alfabéticamente');
}

function editRow(btn) {
  const row  = btn.closest('tr');
  const name = row.cells[1].textContent;
  openModal('form');
  setTimeout(() => {
    const input = document.getElementById('modal-input-name');
    if (input) input.value = name;
  }, 50);
}

// ── Elemento con delay ────────────────────────────────────────────────────────
function showDelayed(ms) {
  const loading = document.getElementById('loading-indicator');
  const element = document.getElementById('delayed-element');

  element.classList.add('hidden');
  loading.classList.remove('hidden');

  setTimeout(() => {
    loading.classList.add('hidden');
    element.classList.remove('hidden');
    log(`Elemento dinámico mostrado después de ${Math.round(ms)}ms`);
  }, ms);
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function log(msg) {
  mutationHistory.push(msg);
  const content = document.getElementById('log-content');
  content.innerHTML = mutationHistory
    .slice(-5)
    .map(m => `<div class="log-entry">▶ ${m}</div>`)
    .join('');
}

function showResult(el, type, msg) {
  el.className = `result-box ${type}`;
  el.textContent = msg;
  el.classList.remove('hidden');
}
