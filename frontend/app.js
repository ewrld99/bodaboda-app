const ACCOUNT_KEY = 'bodaconnect-account';
const roleState = {
  login: 'customer',
  register: 'customer'
};
let riderDashboardRides = [];
let customerDashboardRides = [];
let rideStatusFilter = 'active';
let nearbyRiders = [];
let customerMqttClient = null;
const RIDE_STATUS_TOPIC = 'ride/status';
const MQTT_STATUS_VALUES = ['pending', 'accepted', 'started', 'completed'];

function getAccount() {
  return getSession()?.account || null;
}

function getSession() {
  try {
    const session = JSON.parse(localStorage.getItem(ACCOUNT_KEY));
    if (!session) return null;
    return session.account ? session : { account: session, token: null };
  } catch {
    return null;
  }
}

function getToken() {
  return getSession()?.token || null;
}

function saveSession(account, token) {
  localStorage.setItem(ACCOUNT_KEY, JSON.stringify({ account, token }));
}

function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function logout() {
  localStorage.removeItem(ACCOUNT_KEY);
  window.location.href = 'login.html';
}

function requireRole(role) {
  const account = getAccount();
  const token = getToken();

  if (!account || !token) {
    window.location.href = 'login.html';
    return null;
  }

  if (account.role !== role) {
    window.location.href = account.role === 'rider'
      ? 'rider_dashboard.html'
      : 'customer_dashboard.html';
    return null;
  }

  return account;
}

function dashboardUrl(account) {
  return account?.role === 'rider'
    ? 'rider_dashboard.html'
    : 'customer_dashboard.html';
}

function openDashboard(event) {
  event.preventDefault();
  const account = getAccount();
  const token = getToken();

  window.location.href = account && token
    ? dashboardUrl(account)
    : 'login.html';
}

function updateAuthVisibility() {
  const account = getAccount();
  const token = getToken();
  const signedIn = Boolean(account && token);

  document.querySelectorAll('[data-auth="guest"]').forEach(element => {
    element.hidden = signedIn;
  });

  document.querySelectorAll('[data-auth="user"]').forEach(element => {
    element.hidden = !signedIn;
  });

  document.querySelectorAll('[data-dashboard-link]').forEach(element => {
    element.setAttribute('href', signedIn ? dashboardUrl(account) : 'login.html');
  });
}

function updateActiveNavLink() {
  const page = document.body.dataset.page;
  const activePage = page === 'customer' || page === 'rider' ? 'dashboard' : page;

  document.querySelectorAll('.nav-link').forEach(link => {
    const navPage = link.dataset.navPage;
    link.classList.toggle('active', Boolean(navPage) && !link.hidden && navPage === activePage);
  });
}

function revealProtectedPage() {
  document.querySelectorAll('[data-protected]').forEach(element => {
    element.hidden = false;
  });
}

function setMessage(targetId, message, type) {
  const box = document.getElementById(targetId);
  if (!box) return;

  box.textContent = message;
  box.className = `notice show ${type}`;
}

function setRole(mode, role) {
  roleState[mode] = role;
  ['customer', 'rider'].forEach(option => {
    const button = document.getElementById(`${mode}-${option}-role`);
    if (button) button.classList.toggle('active', option === role);
  });
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function renderRides(rides, targetId, options = {}) {
  const rideList = document.getElementById(targetId);
  if (!rideList) return;

  if (!rides.length) {
    rideList.innerHTML = `<div class="empty">${options.emptyMessage || 'No ride requests yet.'}</div>`;
    return;
  }

  const showStatusActions = Boolean(options.showStatusActions);

  rideList.innerHTML = rides.map(ride => `
    <article class="ride-item">
      <div>
        <div class="ride-id">REQUEST #BC-${String(ride.id).padStart(4, '0')}</div>
        <div class="status-badge">${formatRideStatus(ride.status)}</div>
        <div class="route">
          ${ride.customer_username ? `
          <div class="route-point">
            <span class="route-dot customer-dot"></span>
            <span class="route-label">Customer:</span>
            <span>${escapeHtml(ride.customer_username)}</span>
          </div>
          ` : ''}
          <div class="route-point">
            <span class="route-dot pickup"></span>
            <span class="route-label">Pickup point:</span>
            <span>${escapeHtml(ride.pickup)}</span>
          </div>
          <div class="route-point">
            <span class="route-dot destination"></span>
            <span class="route-label">Destination:</span>
            <span>${escapeHtml(ride.destination)}</span>
          </div>
        </div>
      </div>
      ${showStatusActions && ride.status === 'pending'
        ? `<button class="ride-action" type="button" onclick="updateRideStatus(${ride.id}, 'accepted')">Accept</button>`
        : ''}
      ${showStatusActions && ride.status === 'accepted'
        ? `<button class="ride-action" type="button" onclick="updateRideStatus(${ride.id}, 'started')">Start</button>`
        : ''}
      ${showStatusActions && (ride.status === 'started' || ride.status === 'in_progress')
        ? `<button class="ride-action" type="button" onclick="updateRideStatus(${ride.id}, 'completed')">Complete</button>`
        : ''}
      ${showStatusActions && ride.status === 'completed'
        ? `<button class="ride-action ride-action-danger" type="button" onclick="deleteRide(${ride.id})">Delete</button>`
        : ''}
    </article>
  `).join('');
}

function formatRideStatus(status) {
  if (status === 'pending') return 'Waiting for rider';
  if (status === 'accepted') return 'Accepted';
  if (status === 'started') return 'Started';
  if (status === 'completed') return 'Completed';
  return 'In progress';
}

function renderCustomerDashboardRides() {
  const tripLabel = customerDashboardRides.length === 1
    ? '1 request'
    : `${customerDashboardRides.length} requests`;

  updateText('customer-request-count', tripLabel);
  renderRides(customerDashboardRides, 'customer-ride-list', {
    emptyMessage: 'You have not requested a ride yet.'
  });
}

function applyRideStatusMqttMessage(message) {
  const rideId = Number(message?.ride_id);
  const status = String(message?.status || '').trim().toLowerCase();

  if (!rideId || !MQTT_STATUS_VALUES.includes(status)) return;

  let changed = false;
  customerDashboardRides = customerDashboardRides.map(ride => {
    if (Number(ride.id) !== rideId) return ride;
    changed = true;
    return { ...ride, status };
  });

  if (changed) renderCustomerDashboardRides();
}

function mqttWebSocketUrl() {
  if (window.MQTT_WS_URL) return window.MQTT_WS_URL;

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.hostname || 'localhost';
  return `${protocol}//${host}:9001`;
}

function initCustomerMqttSubscription() {
  if (customerMqttClient || typeof mqtt === 'undefined') return;

  customerMqttClient = mqtt.connect(mqttWebSocketUrl(), {
    clientId: `customer_dashboard_${Date.now()}_${Math.random().toString(16).slice(2)}`,
    connectTimeout: 5000,
    reconnectPeriod: 2000
  });

  customerMqttClient.on('connect', () => {
    customerMqttClient.subscribe(RIDE_STATUS_TOPIC);
  });

  customerMqttClient.on('message', (topic, payload) => {
    if (topic !== RIDE_STATUS_TOPIC) return;

    try {
      applyRideStatusMqttMessage(JSON.parse(payload.toString()));
    } catch (error) {
      console.warn('Invalid MQTT ride status message', error);
    }
  });

  customerMqttClient.on('error', error => {
    console.warn('Could not connect to MQTT broker', error);
  });

  window.addEventListener('beforeunload', () => {
    if (customerMqttClient) customerMqttClient.end(true);
  });
}

function renderRiderDashboardRides() {
  const filteredRides = riderDashboardRides.filter(ride => {
    const status = ride.status || 'pending';
    return rideStatusFilter === 'active'
      ? ['pending', 'accepted', 'started', 'in_progress'].includes(status)
      : status === rideStatusFilter;
  });

  renderRides(filteredRides, 'rider-page-ride-list', {
    showStatusActions: true,
    emptyMessage: rideStatusFilter === 'completed'
      ? 'No completed rides yet.'
      : 'No active rides yet.'
  });
}

function setRideStatusFilter(status) {
  rideStatusFilter = status;
  document.getElementById('in-progress-filter')?.classList.toggle('active', status === 'active');
  document.getElementById('completed-filter')?.classList.toggle('active', status === 'completed');
  renderRiderDashboardRides();
}

function updateRideStatus(rideId, status) {
  fetch(`/api/ride-requests/${rideId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ status })
  })
    .then(response => {
      if (!response.ok) throw new Error('Could not update ride status');
      return response.json();
    })
    .then(updatedRide => {
      riderDashboardRides = riderDashboardRides.map(ride => (
        ride.id === updatedRide.id ? updatedRide : ride
      ));
      renderRiderDashboardRides();
      loadDashboard();
    })
    .catch(() => {
      const riderRideList = document.getElementById('rider-page-ride-list');
      if (riderRideList) {
        riderRideList.insertAdjacentHTML('afterbegin', '<div class="notice show error">Could not update ride status.</div>');
      }
    });
}

function deleteRide(rideId) {
  fetch(`/api/ride-requests/${rideId}`, {
    method: 'DELETE',
    headers: authHeaders()
  })
    .then(response => {
      if (!response.ok) throw new Error('Could not delete ride');
      return response.json();
    })
    .then(() => {
      riderDashboardRides = riderDashboardRides.filter(ride => ride.id !== rideId);
      renderRiderDashboardRides();
      loadDashboard();
    })
    .catch(() => {
      const riderRideList = document.getElementById('rider-page-ride-list');
      if (riderRideList) {
        riderRideList.insertAdjacentHTML('afterbegin', '<div class="notice show error">Could not delete completed ride.</div>');
      }
    });
}

function updateText(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value;
}

function firstName(name) {
  return String(name || '').trim().split(/\s+/)[0] || 'there';
}

function updateNavGreeting(account) {
  updateText('nav-greeting', `Hi, ${firstName(account?.name)}`);
}

function updateAnimatedText(id, value) {
  const element = document.getElementById(id);
  if (!element) return;

  element.textContent = value;
  element.classList.remove('count-pulse');
  void element.offsetWidth;
  element.classList.add('count-pulse');
}

function renderRiderSelects() {
  document.querySelectorAll('[data-rider-select]').forEach(select => {
    if (!nearbyRiders.length) {
      select.innerHTML = '<option value="">No nearby riders available</option>';
      select.disabled = true;
      return;
    }

    select.disabled = false;
    select.innerHTML = [
      '<option value="">Select a nearby rider</option>',
      ...nearbyRiders.map(rider => (
        `<option value="${rider.id}">${escapeHtml(rider.name)}</option>`
      ))
    ].join('');
  });
}

function loadNearbyRiders() {
  if (!document.querySelector('[data-rider-select]')) return Promise.resolve();

  return fetch('/api/riders')
    .then(response => {
      if (!response.ok) throw new Error('Could not load riders');
      return response.json();
    })
    .then(data => {
      nearbyRiders = data.riders || [];
      renderRiderSelects();
    })
    .catch(() => {
      document.querySelectorAll('[data-rider-select]').forEach(select => {
        select.innerHTML = '<option value="">Could not load nearby riders</option>';
        select.disabled = true;
      });
    });
}

function updateDashboard(data) {
  const account = getAccount();
  const rides = data.assigned_trips || [];
  const rider = data.rider || 'Rider';
  const tripLabel = rides.length === 1 ? '1 ride' : `${rides.length} rides`;

  updateText('home-rider-name', rider);
  updateText('home-trip-count', rides.length);
  updateText('request-count', rides.length);
  updateText('customer-request-count', tripLabel);
  updateText('dashboard-rider-name', account?.role === 'rider' ? account.name : rider);
  updateAnimatedText('dashboard-trip-count', tripLabel);
  updateText('rider-page-name', account?.role === 'rider' ? account.name : rider);
  updateText('rider-page-trip-count', rides.length);
  riderDashboardRides = rides.map(ride => ({
    ...ride,
    status: ride.status || 'pending'
  }));
  renderRides(rides, 'ride-list');
  renderRiderDashboardRides();
}

function updateCustomerDashboard(data) {
  const rides = data.assigned_trips || [];
  customerDashboardRides = rides.map(ride => ({
    ...ride,
    status: ride.status || 'pending'
  }));
  renderCustomerDashboardRides();
}

function loadCustomerDashboard() {
  return fetch('/api/customer-dashboard', {
    headers: authHeaders()
  })
    .then(response => {
      if (!response.ok) throw new Error('Could not load customer dashboard');
      return response.json();
    })
    .then(updateCustomerDashboard)
    .catch(() => {
      const customerRideList = document.getElementById('customer-ride-list');
      if (customerRideList) {
        customerRideList.innerHTML = '<div class="empty">Could not load your ride requests.</div>';
      }
    });
}

function updateSiteStats(data) {
  updateText('home-total-trips', data.total_trips ?? 0);
  updateText('home-total-riders', data.total_riders ?? 0);
}

function loadSiteStats() {
  return fetch('/api/site-stats')
    .then(response => {
      if (!response.ok) throw new Error('Could not load site stats');
      return response.json();
    })
    .then(updateSiteStats)
    .catch(() => {
      updateText('home-total-trips', 'Unavailable');
      updateText('home-total-riders', 'Unavailable');
    });
}

function loadDashboard() {
  return fetch('/api/rider-dashboard', {
    headers: authHeaders()
  })
    .then(response => {
      if (!response.ok) throw new Error('Could not load dashboard');
      return response.json();
    })
    .then(updateDashboard)
    .catch(() => {
      const message = '<div class="empty">Could not load ride requests.</div>';
      const rideList = document.getElementById('ride-list');
      const riderRideList = document.getElementById('rider-page-ride-list');
      if (rideList) rideList.innerHTML = message;
      if (riderRideList) riderRideList.innerHTML = message;
    });
}

function requestRide(event) {
  event.preventDefault();
  const form = event.target;
  const pickupInput = form.elements.pickup;
  const destinationInput = form.elements.destination;
  const riderInput = form.elements.rider_id;
  const messageTarget = form.dataset.messageTarget || 'ride-message';
  const pickup = pickupInput.value.trim();
  const destination = destinationInput.value.trim();
  const riderId = riderInput?.value;

  if (!pickup || !destination || !riderId) {
    setMessage(messageTarget, 'Pickup, destination, and nearby rider are required.', 'error');
    return;
  }

  fetch('/api/request-ride', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ pickup, destination, rider_id: riderId })
  })
    .then(response => {
      if (!response.ok) throw new Error('Could not save ride request');
      return response.json();
    })
    .then(data => {
      setMessage(messageTarget, `Ride request #${data.id} sent to ${data.rider_name}.`, 'ok');
      pickupInput.value = '';
      destinationInput.value = '';
      if (riderInput) riderInput.value = '';
      return document.body.dataset.page === 'customer'
        ? loadCustomerDashboard()
        : loadDashboard();
    })
    .catch(() => {
      setMessage(messageTarget, 'Could not save the ride request.', 'error');
    });
}

function registerAccount(event) {
  event.preventDefault();
  const firstName = document.getElementById('register-first-name').value.trim();
  const lastName = document.getElementById('register-last-name').value.trim();
  const email = document.getElementById('register-email').value.trim();
  const password = document.getElementById('register-password').value;
  const role = roleState.register;

  if (!firstName || !lastName || !email || !password) {
    setMessage('auth-message', 'First name, last name, email, and password are required.', 'error');
    return;
  }

  fetch('/api/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ first_name: firstName, last_name: lastName, email, password, role })
  })
    .then(async response => {
      const json = await response.json().catch(() => null);
      if (!response.ok) {
        const err = (json && (json.error || json.message)) || 'Could not create account';
        throw new Error(err);
      }
      return json;
    })
    .then(data => {
      saveSession(data.account, data.token);
      window.location.href = data.account.role === 'rider'
        ? 'rider_dashboard.html'
        : 'customer_dashboard.html';
    })
    .catch((err) => {
      setMessage('auth-message', err?.message || 'Could not create the account. The email may already be registered.', 'error');
    });
}

function loginAccount(event) {
  event.preventDefault();
  const email = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;
  const role = roleState.login;

  if (!email || !password) {
    setMessage('auth-message', 'Email and password are required.', 'error');
    return;
  }

  fetch('/api/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, role })
  })
    .then(async response => {
      const json = await response.json().catch(() => null);
      if (!response.ok) {
        const message = (json && (json.error || json.message)) || 'Could not login';
        throw new Error(message);
      }
      return json;
    })
    .then(data => {
      saveSession(data.account, data.token);
      window.location.href = data.account.role === 'rider'
        ? 'rider_dashboard.html'
        : 'customer_dashboard.html';
    })
    .catch((error) => {
      setMessage('auth-message', error?.message || 'Login failed. Check your role, email, and password.', 'error');
    });
}

function initPage() {
  const page = document.body.dataset.page;
  const account = getAccount();
  const token = getToken();

  updateAuthVisibility();
  updateActiveNavLink();

  if ((page === 'login' || page === 'registration') && account && token) {
    window.location.href = dashboardUrl(account);
    return;
  }

  if (page === 'customer') {
    const customer = requireRole('customer');
    if (!customer) return;
    revealProtectedPage();
    updateNavGreeting(customer);
    updateText('customer-title', 'Customer page');
    loadNearbyRiders();
    loadCustomerDashboard();
    initCustomerMqttSubscription();
  }

  if (page === 'rider') {
    const rider = requireRole('rider');
    if (!rider) return;
    revealProtectedPage();
    updateNavGreeting(rider);
    loadDashboard();
  }

  if (page === 'home') {
    loadSiteStats();
  }

  if (page === 'login' || page === 'registration') {
    updateText('session-name', account?.name || 'Guest');
    updateText(
      'session-role',
      account ? `Logged in as ${account.role}.` : 'Login as a customer or rider.'
    );
  }

  // highlight numeric text across the page
  try { highlightNumbers(); } catch (e) { /* fail silently */ }
}

document.addEventListener('DOMContentLoaded', initPage);

// Wrap numeric sequences in a span.num so numbers can be styled via CSS
function highlightNumbers() {
  if (!document.body) return;
  const skipTags = new Set(['SCRIPT','STYLE','NOSCRIPT','TEXTAREA','INPUT','SELECT','BUTTON','A','CODE','PRE','SVG']);

  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.nodeValue || !/\d/.test(node.nodeValue)) return NodeFilter.FILTER_REJECT;
      const parent = node.parentNode;
      if (!parent) return NodeFilter.FILTER_REJECT;
      if (parent.nodeType !== 1) return NodeFilter.FILTER_REJECT;
      const tag = parent.nodeName;
      if (skipTags.has(tag)) return NodeFilter.FILTER_REJECT;
      if (parent.closest && parent.closest('[data-no-number-highlight]')) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    }
  });

  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);

  const re = /(\d[\d,\.\/%]*)/g;

  nodes.forEach(textNode => {
    const parts = textNode.nodeValue.split(re);
    if (parts.length === 1) return;
    const frag = document.createDocumentFragment();
    parts.forEach(part => {
      if (!part) return;
      if (re.test(part)) {
        const span = document.createElement('span');
        span.className = 'num';
        span.textContent = part;
        frag.appendChild(span);
      } else {
        frag.appendChild(document.createTextNode(part));
      }
    });
    textNode.parentNode.replaceChild(frag, textNode);
  });
}
