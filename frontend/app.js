// Irium Frontend JavaScript - ChatGPT Style

// State Management
let currentChatId = null;
let chatHistory = [];
let uploadedFiles = [];
let isProcessing = false;
let currentRequestController = null; // For aborting requests
let currentUser = null; // User session
const API_BASE_URL = window.location.protocol === 'file:' ? 'http://127.0.0.1:8000' : '';

function apiUrl(path) {
    return `${API_BASE_URL}${path}`;
}

// DOM Elements
const welcomeScreen = document.getElementById('welcomeScreen');
const messagesContainer = document.getElementById('messagesContainer');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const newChatBtn = document.getElementById('newChatBtn');
const attachBtn = document.getElementById('attachBtn');
const fileInput = document.getElementById('fileInput');
const fileCount = document.getElementById('fileCount');

// Document Intelligence DOM Elements
const inputErrorBanner = document.getElementById('inputErrorBanner');
const inputErrorText = document.getElementById('inputErrorText');
const closeErrorBannerBtn = document.getElementById('closeErrorBannerBtn');
const activeDocBanner = document.getElementById('activeDocBanner');
const activeDocName = document.getElementById('activeDocName');
const activeDocPages = document.getElementById('activeDocPages');
const detachDocBtn = document.getElementById('detachDocBtn');
const uploadProgressContainer = document.getElementById('uploadProgressContainer');
const progressBarFill = document.getElementById('progressBarFill');
const progressStatusText = document.getElementById('progressStatusText');
const attachmentPreviewTray = document.getElementById('attachmentPreviewTray');
// Bottom-Left Auth Elements
const sidebarFooter = document.getElementById('sidebarFooter');
const authLoggedOut = document.getElementById('authLoggedOut');
const authLoggedIn = document.getElementById('authLoggedIn');
const loginSignupBtn = document.getElementById('loginSignupBtn');
const userAvatar = document.getElementById('userAvatar');
const userDisplayName = document.getElementById('userDisplayName');
const userDisplayEmail = document.getElementById('userDisplayEmail');
const logoutBtn = document.getElementById('logoutBtn');

// Auth Modal Elements
const authModal = document.getElementById('authModal');
const authBackdrop = document.getElementById('authBackdrop');
const closeAuthBtn = document.getElementById('closeAuthBtn');
const authForm = document.getElementById('authForm');
const authTitle = document.getElementById('authTitle');
const authSubtitle = document.getElementById('authSubtitle');
const authSubmit = document.getElementById('authSubmit');
const authSubmitText = document.getElementById('authSubmitText');
const authError = document.getElementById('authError');
const authSuccess = document.getElementById('authSuccess');
const signinTab = document.getElementById('signinTab');
const signupTab = document.getElementById('signupTab');
const signupFields = document.getElementById('signupFields');
const authToggleBtn = document.getElementById('authToggleBtn');
const authToggleText = document.getElementById('authToggleText');
const authEmail = document.getElementById('authEmail');
const authPassword = document.getElementById('authPassword');
const authUsername = document.getElementById('authUsername');
const authFullName = document.getElementById('authFullName');

const stopBtn = document.getElementById('stopBtn');
const inputWrapper = document.getElementById('inputWrapper');
let authMode = 'signin';

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadChatHistory();
    setupEventListeners();
    autoResizeTextarea();
    restoreAuthSession();
    checkUrlPrompt();
    updateActiveDocBanner();
});

function checkUrlPrompt() {
    try {
        const urlParams = new URLSearchParams(window.location.search);
        const initialPrompt = urlParams.get('prompt') || urlParams.get('q');
        if (initialPrompt && messageInput) {
            messageInput.value = initialPrompt;
            autoResizeTextarea();
            toggleSendButton();
            messageInput.focus();
        }
    } catch (e) {
        console.error('Error parsing initial prompt:', e);
    }
}

// Event Listeners
function setupEventListeners() {
    // Send message
    sendBtn.addEventListener('click', handleSendMessage);
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    });

    // Input change
    messageInput.addEventListener('input', () => {
        autoResizeTextarea();
        toggleSendButton();
    });

    // New chat
    newChatBtn.addEventListener('click', startNewChat);

    // File attachment
    attachBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFileSelection);

    // Stop button
    stopBtn.addEventListener('click', handleStopGeneration);

    // Document Intelligence listeners
    if (closeErrorBannerBtn) {
        closeErrorBannerBtn.addEventListener('click', hideInputError);
    }
    if (detachDocBtn) {
        detachDocBtn.addEventListener('click', detachCurrentDocument);
    }

    // Bottom-Left Auth Controls
    if (loginSignupBtn) {
        loginSignupBtn.addEventListener('click', () => openAuthModal('signin'));
    }
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleSignOut);
    }
    if (closeAuthBtn) {
        closeAuthBtn.addEventListener('click', closeAuthModal);
    }
    if (authBackdrop) {
        authBackdrop.addEventListener('click', closeAuthModal);
    }
    if (signinTab) {
        signinTab.addEventListener('click', () => setAuthMode('signin'));
    }
    if (signupTab) {
        signupTab.addEventListener('click', () => setAuthMode('signup'));
    }
    if (authToggleBtn) {
        authToggleBtn.addEventListener('click', () => {
            setAuthMode(authMode === 'signin' ? 'signup' : 'signin');
        });
    }
    if (authForm) {
        authForm.addEventListener('submit', handleAuthSubmit);
    }

    // Modal keyboard accessibility
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && authModal && !authModal.hasAttribute('hidden')) {
            closeAuthModal();
        }
    });

    // Example prompts
    document.querySelectorAll('.prompt-card').forEach(card => {
        card.addEventListener('click', () => {
            const prompt = card.getAttribute('data-prompt');
            messageInput.value = prompt;
            autoResizeTextarea();
            toggleSendButton();
            messageInput.focus();
        });
    });
}

// ============================================================================
// JWT Authentication Implementation
// ============================================================================

function authHeaders() {
    const token = localStorage.getItem('irium_token') || localStorage.getItem('irium_access_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
}

function openAuthModal(mode = 'signin') {
    if (!authModal) return;
    setAuthMode(mode);
    clearAuthMessages();
    authModal.removeAttribute('hidden');
    setTimeout(() => {
        if (authEmail) authEmail.focus();
    }, 60);
}

function closeAuthModal() {
    if (!authModal) return;
    authModal.setAttribute('hidden', '');
    if (authForm) authForm.reset();
    clearAuthMessages();
}

function clearAuthMessages() {
    if (authError) {
        authError.style.display = 'none';
        authError.textContent = '';
    }
    if (authSuccess) {
        authSuccess.style.display = 'none';
        authSuccess.textContent = '';
    }
}

function setAuthMode(mode) {
    authMode = mode;
    clearAuthMessages();
    const isSignup = mode === 'signup';

    if (signinTab) signinTab.classList.toggle('active', !isSignup);
    if (signupTab) signupTab.classList.toggle('active', isSignup);
    if (signupFields) signupFields.style.display = isSignup ? 'block' : 'none';
    if (authUsername) authUsername.required = isSignup;

    if (authTitle) {
        authTitle.textContent = 'IRIUM';
    }
    if (authSubtitle) {
        authSubtitle.textContent = isSignup ? 'Create a new account' : 'Sign in to your account';
    }
    if (authSubmitText) {
        authSubmitText.textContent = isSignup ? 'Create Account' : 'Sign in';
    }
    if (authToggleText) {
        authToggleText.textContent = isSignup ? 'Already have an account?' : "Don't have an account?";
    }
    if (authToggleBtn) {
        authToggleBtn.textContent = isSignup ? 'Sign in' : 'Create one';
    }
}

async function handleAuthSubmit(event) {
    event.preventDefault();
    clearAuthMessages();

    const email = authEmail ? authEmail.value.trim() : '';
    const password = authPassword ? authPassword.value : '';
    const username = authUsername ? authUsername.value.trim() : '';
    const full_name = authFullName ? authFullName.value.trim() : '';

    if (!email || !password) {
        showAuthError('Please fill in both email and password.');
        return;
    }

    if (password.length < 6) {
        showAuthError('Password must be at least 6 characters.');
        return;
    }

    if (authMode === 'signup' && !username) {
        showAuthError('Please provide a username for registration.');
        return;
    }

    if (authSubmit) authSubmit.disabled = true;
    if (authSubmitText) {
        authSubmitText.textContent = authMode === 'signup' ? 'Creating account...' : 'Signing in...';
    }

    const payload = { email, password };
    if (authMode === 'signup') {
        payload.username = username;
        payload.full_name = full_name || null;
    }

    try {
        const endpoint = authMode === 'signup' ? '/api/auth/signup' : '/api/auth/signin';
        const response = await fetch(apiUrl(endpoint), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (!response.ok) {
            const errorMsg = data.detail || 'Authentication failed. Please check your credentials.';
            showAuthError(errorMsg);
            return;
        }

        // Store JWT token and user info
        localStorage.setItem('irium_token', data.access_token);
        localStorage.setItem('irium_access_token', data.access_token);
        localStorage.setItem('irium_user', JSON.stringify(data.user));
        currentUser = data.user;

        // Feedback banner
        if (authSuccess) {
            authSuccess.textContent = authMode === 'signup' 
                ? 'Account created successfully! Signed in.' 
                : 'Welcome back! Signed in successfully.';
            authSuccess.style.display = 'block';
        }

        renderAuthState();

        // Close modal smoothly after brief success feedback
        setTimeout(() => {
            closeAuthModal();
        }, 600);

    } catch (error) {
        console.error('Auth request error:', error);
        showAuthError('Connection error. Could not connect to authentication server.');
    } finally {
        if (authSubmit) authSubmit.disabled = false;
        if (authSubmitText) {
            authSubmitText.textContent = authMode === 'signup' ? 'Create Account' : 'Sign in';
        }
    }
}

function showAuthError(message) {
    if (authError) {
        authError.textContent = message;
        authError.style.display = 'block';
    }
}

async function restoreAuthSession() {
    const token = localStorage.getItem('irium_token') || localStorage.getItem('irium_access_token');
    if (!token) {
        currentUser = null;
        renderAuthState();
        return;
    }

    try {
        const response = await fetch(apiUrl('/api/auth/me'), {
            headers: authHeaders()
        });

        if (response.ok) {
            currentUser = await response.json();
            localStorage.setItem('irium_user', JSON.stringify(currentUser));
        } else {
            // Token expired or invalid
            localStorage.removeItem('irium_token');
            localStorage.removeItem('irium_access_token');
            localStorage.removeItem('irium_user');
            currentUser = null;
        }
    } catch (error) {
        console.warn('Could not verify JWT token with server:', error);
        const cachedUser = localStorage.getItem('irium_user');
        if (cachedUser) {
            try {
                currentUser = JSON.parse(cachedUser);
            } catch (e) {
                currentUser = null;
            }
        }
    }

    renderAuthState();
}

async function handleSignOut() {
    const token = localStorage.getItem('irium_token') || localStorage.getItem('irium_access_token');
    try {
        if (token) {
            await fetch(apiUrl('/api/auth/signout'), {
                method: 'POST',
                headers: authHeaders()
            });
        }
    } catch (e) {
        // Signout on server is best effort
    }

    localStorage.removeItem('irium_token');
    localStorage.removeItem('irium_access_token');
    localStorage.removeItem('irium_user');
    currentUser = null;
    renderAuthState();
}

function renderAuthState() {
    if (!authLoggedOut || !authLoggedIn) return;

    if (currentUser) {
        authLoggedOut.style.setProperty('display', 'none', 'important');
        authLoggedOut.classList.add('hidden');
        authLoggedIn.style.setProperty('display', 'flex', 'important');
        authLoggedIn.classList.remove('hidden');

        const displayName = currentUser.full_name || currentUser.username || (currentUser.email ? currentUser.email.split('@')[0] : 'User');
        const displayEmail = currentUser.email || '';
        const initial = (displayName.charAt(0) || 'U').toUpperCase();

        if (userAvatar) userAvatar.textContent = initial;
        if (userDisplayName) userDisplayName.textContent = displayName;
        if (userDisplayEmail) userDisplayEmail.textContent = displayEmail;
    } else {
        authLoggedIn.style.setProperty('display', 'none', 'important');
        authLoggedIn.classList.add('hidden');
        authLoggedOut.style.setProperty('display', 'flex', 'important');
        authLoggedOut.classList.remove('hidden');
    }
}

// Auto-resize textarea
function autoResizeTextarea() {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 200) + 'px';
}

// Toggle send button
function toggleSendButton() {
    const hasText = messageInput && messageInput.value.trim().length > 0;
    const hasFiles = uploadedFiles && uploadedFiles.length > 0;
    if (sendBtn) {
        sendBtn.disabled = (!hasText && !hasFiles) || isProcessing;
    }
}

// Start new chat
function startNewChat() {
    if (currentRequestController) {
        currentRequestController.abort();
        currentRequestController = null;
    }

    currentChatId = generateChatId();
    uploadedFiles = [];
    renderAttachmentChips();
    hideInputError();
    hideUploadProgress();
    updateActiveDocBanner();
    messagesContainer.innerHTML = '';
    messageInput.value = '';
    autoResizeTextarea();
    setProcessingState(false);
    welcomeScreen.style.display = 'flex';
    updateFileCount();
    messageInput.focus();
}

// Handle send message
async function handleSendMessage() {
    let message = messageInput.value.trim();
    const hasFiles = uploadedFiles.length > 0;
    const activeDoc = getActiveSessionDoc(currentChatId);

    if (!message && !hasFiles) return;
    if (isProcessing) return;

    // Default question if user uploaded file without typing text
    if (!message && hasFiles) {
        message = "Summarize this document and highlight key findings, figures, and major financial risks.";
    }

    hideInputError();
    welcomeScreen.style.display = 'none';

    // Add user message (with attached file badges if any)
    let displayMessage = message;
    if (hasFiles) {
        const fileBadges = uploadedFiles.map(f => `📎 [${escapeHtml(f.name)}]`).join(' ');
        displayMessage = `${escapeHtml(message)}\n\n${fileBadges}`;
    }

    addMessage('user', displayMessage);

    // Clear input
    messageInput.value = '';
    autoResizeTextarea();
    toggleSendButton();

    // Set processing state
    setProcessingState(true);

    try {
        if (hasFiles) {
            // New document upload & analysis mode
            await handleDocumentAnalysis(message);
        } else if (activeDoc) {
            // Follow-up question about the document in this conversation
            await handleDocumentFollowUp(message);
        } else {
            // Standard financial research mode
            await handleResearch(message);
        }
    } catch (error) {
        console.error('Error:', error);
        const errorMessage = error.message || JSON.stringify(error);
        if (errorMessage.includes('rate_limit') || errorMessage.includes('429')) {
            addMessage('assistant', '⚠️ Rate limit reached. The system is automatically retrying with a backup model. Please try your query again in a moment.');
        } else {
            showInputError(error.message || 'Failed to process request.');
            addMessage('assistant', `❌ Error: ${error.message || 'Sorry, I encountered an issue processing your request.'}`);
        }
    } finally {
        setProcessingState(false);
        hideUploadProgress();
    }

    // Save to history
    saveChatHistory(message);
}

// Set processing state
function setProcessingState(processing) {
    isProcessing = processing;
    
    if (processing) {
        // Show stop button, hide send button
        sendBtn.style.display = 'none';
        stopBtn.style.display = 'flex';
        
        // Disable input
        inputWrapper.classList.add('disabled');
        messageInput.disabled = true;
        attachBtn.disabled = true;
    } else {
        // Hide stop button, show send button
        stopBtn.style.display = 'none';
        sendBtn.style.display = 'flex';
        
        // Enable input
        inputWrapper.classList.remove('disabled');
        messageInput.disabled = false;
        attachBtn.disabled = false;
        
        // Reset controller
        currentRequestController = null;
    }
    
    toggleSendButton();
}

// Handle stop generation
function handleStopGeneration() {
    if (currentRequestController) {
        currentRequestController.abort();
        currentRequestController = null;
    }
    hideUploadProgress();
    setProcessingState(false);
}

// Extract conversation turns for reference resolution
function getRecentConversationTurns() {
    const turns = [];
    const messageElements = messagesContainer.querySelectorAll('.message');
    messageElements.forEach(el => {
        const isUser = el.classList.contains('user');
        const text = el.querySelector('.message-content') ? el.querySelector('.message-content').innerText : '';
        if (text) {
            turns.push({
                role: isUser ? 'user' : 'assistant',
                content: text.slice(0, 300)
            });
        }
    });
    return turns.slice(-4);
}

// Handle research request
async function handleResearch(query) {
    const loadingId = addLoadingMessage();
    currentRequestController = new AbortController();

    try {
        const response = await fetch(apiUrl('/api/research'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...authHeaders(),
            },
            body: JSON.stringify({ query }),
            signal: currentRequestController.signal,
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        removeMessage(loadingId);
        addResearchMessage(data);

    } catch (error) {
        removeMessage(loadingId);
        if (error.name !== 'AbortError') {
            throw error;
        } else {
            addMessage('assistant', '⚠️ Generation stopped by user.');
        }
    }
}

// Handle document analysis request with upload
async function handleDocumentAnalysis(query) {
    const loadingId = addLoadingMessage();
    currentRequestController = new AbortController();
    showUploadProgress(25, 'Uploading and validating documents...');

    try {
        const formData = new FormData();
        formData.append('query', query);
        formData.append('session_id', currentChatId);
        formData.append('conversation_history', JSON.stringify(getRecentConversationTurns()));

        uploadedFiles.forEach(file => {
            formData.append('files', file);
        });

        showUploadProgress(55, 'Extracting text, tables, and visual layout...');

        const response = await fetch(apiUrl('/api/documents/analyze'), {
            method: 'POST',
            headers: authHeaders(),
            body: formData,
            signal: currentRequestController.signal,
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            const errMsg = typeof errData.detail === 'string' ? errData.detail : (errData.detail?.message || `Upload failed (${response.status})`);
            throw new Error(errMsg);
        }

        showUploadProgress(85, 'Synthesizing evidence and insights...');
        const data = await response.json();
        
        showUploadProgress(100, 'Analysis complete!');
        setTimeout(hideUploadProgress, 800);

        removeMessage(loadingId);
        addDocumentAnalysisMessage(data);

        // Save active document state for this conversation
        if (data.documents && data.documents.length > 0) {
            saveActiveSessionDoc(currentChatId, {
                docId: data.primary_document_id || (data.document_ids && data.document_ids[0]) || '',
                filename: data.documents.join(', '),
                pageCount: data.metadata?.page_count || 1
            });
            updateActiveDocBanner();
        }

        // Clear uploaded files after processing
        uploadedFiles = [];
        renderAttachmentChips();
        updateFileCount();

    } catch (error) {
        hideUploadProgress();
        removeMessage(loadingId);
        if (error.name !== 'AbortError') {
            throw error;
        } else {
            addMessage('assistant', '⚠️ Generation stopped by user.');
        }
    }
}

// Handle follow-up questions for existing document in conversation
async function handleDocumentFollowUp(query) {
    const loadingId = addLoadingMessage();
    currentRequestController = new AbortController();
    showUploadProgress(40, 'Searching active document evidence...');

    try {
        const activeDoc = getActiveSessionDoc(currentChatId);
        const formData = new FormData();
        formData.append('query', query);
        formData.append('session_id', currentChatId);
        if (activeDoc && activeDoc.docId) {
            formData.append('document_id', activeDoc.docId);
        }
        formData.append('conversation_history', JSON.stringify(getRecentConversationTurns()));

        showUploadProgress(70, 'Retrieving relevant pages and generating answer...');

        const response = await fetch(apiUrl('/api/documents/analyze'), {
            method: 'POST',
            headers: authHeaders(),
            body: formData,
            signal: currentRequestController.signal,
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            const errMsg = typeof errData.detail === 'string' ? errData.detail : (errData.detail?.message || `Follow-up failed (${response.status})`);
            throw new Error(errMsg);
        }

        showUploadProgress(100, 'Done!');
        setTimeout(hideUploadProgress, 600);

        const data = await response.json();
        removeMessage(loadingId);
        addDocumentAnalysisMessage(data);

    } catch (error) {
        hideUploadProgress();
        removeMessage(loadingId);
        if (error.name !== 'AbortError') {
            throw error;
        } else {
            addMessage('assistant', '⚠️ Generation stopped by user.');
        }
    }
}

// Add message to chat
function addMessage(role, content, metadata = {}) {
    const messageId = generateMessageId();
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    messageDiv.id = messageId;

    const avatar = role === 'user' ? 'You' : 'AI';
    const avatarInitial = role === 'user' ? 'Y' : 'I';

    const renderedContent = role === 'user'
        ? formatMessage(content, metadata, 'user')
        : formatMarkdown(content);

    messageDiv.innerHTML = `
        <div class="message-header">
            <div class="message-avatar">${avatarInitial}</div>
            <div class="message-author">${avatar}</div>
        </div>
        <div class="message-content">
            ${renderedContent}
        </div>
    `;

    messagesContainer.appendChild(messageDiv);
    scrollToBottom();
    
    // Auto-save messages
    if (currentChatId) {
        saveCurrentChatMessages();
    }

    return messageId;
}

// Add research message with metadata
function addResearchMessage(data) {
    const messageId = generateMessageId();
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.id = messageId;

    let content = '';

    // Handle structured answer format
    if (data.answer && typeof data.answer === 'object' && data.answer.sections) {
        content = formatMarkdown(data.answer);
    } else if (typeof data.answer === 'string') {
        content = formatMarkdown(data.answer);
    } else {
        content = '<p>Invalid response format</p>';
    }

    // Add sources if available (from data.sources or data.answer.sources)
    const sources = data.sources || (data.answer && data.answer.sources) || [];
    if (sources.length > 0) {
        content += '<div class="sources">';
        content += '<div class="sources-title">Sources:</div>';
        content += '<div class="source-list">';
        sources.forEach((source) => {
            const sourceUrl = source.url || source.source_url || '#';
            const sourceTitle = source.title || source.source_title || source.name || source.source_name || sourceUrl;
            content += `
                <a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener" class="source-link">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                        <polyline points="15 3 21 3 21 9" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                        <line x1="10" y1="14" x2="21" y2="3" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    ${escapeHtml(sourceTitle)}
                </a>
            `;
        });
        content += '</div></div>';
    }

    messageDiv.innerHTML = `
        <div class="message-header">
            <div class="message-avatar">I</div>
            <div class="message-author">Irium</div>
        </div>
        <div class="message-content">
            ${content}
        </div>
    `;

    messagesContainer.appendChild(messageDiv);
    scrollToBottom();
    
    // Auto-save messages
    if (currentChatId) {
        saveCurrentChatMessages();
    }

    return messageId;
}

// Add document analysis message
function addDocumentAnalysisMessage(data) {
    const messageId = generateMessageId();
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.id = messageId;

    let formattedAnswer = formatMarkdown(data.answer);

    // Highlight [Page X] citations as interactive pills
    formattedAnswer = formattedAnswer.replace(/\[Page\s+(\d+)\]/gi, (match, pNum) => {
        return `<span class="citation-pill">📄 Page ${pNum}</span>`;
    });
    formattedAnswer = formattedAnswer.replace(/\[([^\]]+,\s*Page\s+\d+)\]/gi, (match, fullRef) => {
        return `<span class="citation-pill">📄 ${escapeHtml(fullRef)}</span>`;
    });
    formattedAnswer = formattedAnswer.replace(/\[Page\s+\d+\s+Visual\s+Analysis\]/gi, (match) => {
        return `<span class="citation-pill image-ref">🖼️ Visual Analysis</span>`;
    });

    let content = `
        ${formattedAnswer}
    `;

    // Add document sources and cited pages
    const isGeneralQuery = Boolean(data.metadata && data.metadata.is_general_query);
    const hasDocs = !isGeneralQuery && data.documents && data.documents.length > 0;
    const hasPages = !isGeneralQuery && data.source_pages && data.source_pages.length > 0;

    if (hasDocs || hasPages) {
        content += '<div class="sources">';
        content += '<div class="sources-title">Document Evidence:</div>';
        content += '<div class="source-list">';

        if (hasDocs) {
            data.documents.forEach(doc => {
                content += `<div class="source-link">📄 ${escapeHtml(doc)}</div>`;
            });
        }

        if (hasPages) {
            const pageTags = data.source_pages.map(p => `<span class="citation-pill">Page ${p}</span>`).join(' ');
            content += `<div style="margin-top: 4px; font-size: 12px; color: var(--text-secondary);">Pages referenced: ${pageTags}</div>`;
        }

        content += '</div></div>';
    }

    messageDiv.innerHTML = `
        <div class="message-header">
            <div class="message-avatar">I</div>
            <div class="message-author">Irium</div>
        </div>
        <div class="message-content">
            ${content}
        </div>
    `;

    messagesContainer.appendChild(messageDiv);
    scrollToBottom();

    // Auto-save messages to preserve in chat history
    if (currentChatId) {
        saveCurrentChatMessages();
    }

    return messageId;
}

// Add loading message
function addLoadingMessage() {
    const messageId = generateMessageId();
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.id = messageId;

    messageDiv.innerHTML = `
        <div class="message-header">
            <div class="message-avatar">I</div>
            <div class="message-author">Irium</div>
        </div>
        <div class="message-content">
            <div class="loading-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;

    messagesContainer.appendChild(messageDiv);
    scrollToBottom();

    return messageId;
}

// Remove message
function removeMessage(messageId) {
    const message = document.getElementById(messageId);
    if (message) {
        message.remove();
    }
}

// Format message content
function formatMessage(content, metadata = {}, role = 'assistant') {
    if (role === 'user') {
        const escaped = escapeHtml(content || '');
        return escaped.split('\n\n').map(para => `<p>${para.replace(/\n/g, '<br>')}</p>`).join('');
    }
    return formatMarkdown(content);
}

// Render markdown and structured answer format
function formatMarkdown(answer) {
    if (!answer) return '';

    // Check if answer is structured JSON format
    if (typeof answer === 'object' && answer.sections) {
        // Check if any section contains nested JSON in its content
        let hasNestedJson = false;
        if (Array.isArray(answer.sections)) {
            for (let section of answer.sections) {
                if (section.content && typeof section.content === 'string') {
                    const content = section.content.trim();
                    // Check if content is JSON
                    if (content.startsWith('{') && content.includes('sections')) {
                        try {
                            const parsedContent = JSON.parse(content);
                            if (parsedContent.sections && Array.isArray(parsedContent.sections)) {
                                console.log('Detected nested JSON in section content, parsing as structured data');
                                return `<div class="markdown-content">${renderStructuredAnswer(parsedContent)}</div>`;
                            }
                        } catch (e) {
                            // Not valid JSON, continue with normal rendering
                        }
                    }
                }
            }
        }
        
        // No nested JSON found, render normally
        return `<div class="markdown-content">${renderStructuredAnswer(answer)}</div>`;
    }

    if (typeof answer !== 'string') {
        answer = String(answer);
    }

    // Check if the string content looks like JSON and try to parse it
    if (answer.trim().startsWith('{') && answer.includes('sections') && answer.includes('type')) {
        try {
            const parsedAnswer = JSON.parse(answer);
            if (parsedAnswer.sections && Array.isArray(parsedAnswer.sections)) {
                console.log('Detected embedded JSON in string content, parsing as structured data');
                return `<div class="markdown-content">${renderStructuredAnswer(parsedAnswer)}</div>`;
            }
        } catch (e) {
            console.warn('Content looks like JSON but failed to parse:', e);
            // Continue with regular text processing
        }
    }

    let parsedHtml = '';

    if (typeof marked !== 'undefined' && marked.parse) {
        try {
            // Configure marked with GFM, breaks, and custom table wrapper hook
            marked.use({
                gfm: true,
                breaks: true,
                hooks: {
                    postprocess(html) {
                        // Wrap all <table> elements in .markdown-table-wrapper for horizontal scroll
                        return html.replace(/<table(\s*[^>]*)?>([\s\S]*?)<\/table>/gi, (match) => {
                            return `<div class="markdown-table-wrapper">${match}</div>`;
                        });
                    }
                }
            });

            parsedHtml = marked.parse(answer);
        } catch (err) {
            console.error('Error in marked parser:', err);
            parsedHtml = fallbackMarkdownParse(answer);
        }
    } else {
        parsedHtml = fallbackMarkdownParse(answer);
    }

    // Highlight [Page X] citations as interactive pills
    parsedHtml = parsedHtml.replace(/\[Page\s+(\d+)\]/gi, (match, pNum) => {
        return `<span class="citation-pill">📄 Page ${pNum}</span>`;
    });
    parsedHtml = parsedHtml.replace(/\[([^\]]+,\s*Page\s+\d+)\]/gi, (match, fullRef) => {
        return `<span class="citation-pill">📄 ${escapeHtml(fullRef)}</span>`;
    });
    parsedHtml = parsedHtml.replace(/\[Page\s+\d+\s+Visual\s+Analysis\]/gi, () => {
        return `<span class="citation-pill image-ref">🖼️ Visual Analysis</span>`;
    });

    // Sanitize with DOMPurify if available
    if (typeof DOMPurify !== 'undefined' && DOMPurify.sanitize) {
        parsedHtml = DOMPurify.sanitize(parsedHtml, {
            ADD_ATTR: ['target', 'rel', 'class', 'style'],
            ADD_TAGS: ['span', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'div', 'input']
        });
    }

    return `<div class="markdown-content">${parsedHtml}</div>`;
}

// Fallback basic markdown parser if marked library is not available
function fallbackMarkdownParse(text) {
    if (!text) return '';
    let codeBlocks = [];
    text = text.replace(/```([a-z0-9_-]*)\n([\s\S]*?)```/gi, (match, lang, code) => {
        const id = `__CODE_BLOCK_${codeBlocks.length}__`;
        codeBlocks.push(`<pre><code class="language-${escapeHtml(lang)}">${escapeHtml(code.trim())}</code></pre>`);
        return id;
    });

    let inlineCodes = [];
    text = text.replace(/`([^`]+)`/g, (match, code) => {
        const id = `__INLINE_CODE_${inlineCodes.length}__`;
        inlineCodes.push(`<code>${escapeHtml(code)}</code>`);
        return id;
    });

    text = text.replace(/^###### (.*$)/gim, '<h6>$1</h6>');
    text = text.replace(/^##### (.*$)/gim, '<h5>$1</h5>');
    text = text.replace(/^#### (.*$)/gim, '<h4>$1</h4>');
    text = text.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    text = text.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    text = text.replace(/^# (.*$)/gim, '<h1>$1</h1>');

    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
    text = text.replace(/~~(.*?)~~/g, '<del>$1</del>');

    inlineCodes.forEach((c, i) => {
        text = text.replace(`__INLINE_CODE_${i}__`, c);
    });
    codeBlocks.forEach((c, i) => {
        text = text.replace(`__CODE_BLOCK_${i}__`, c);
    });

    return text.split('\n\n').map(p => p.trim() ? `<p>${p.replace(/\n/g, '<br>')}</p>` : '').join('');
}

// Render structured answer with sections and tables
function renderStructuredAnswer(data) {
    if (!data.sections || !Array.isArray(data.sections)) {
        console.warn('Invalid structured answer format:', data);
        return '<p>Invalid response format</p>';
    }

    let html = '';

    data.sections.forEach((section, index) => {
        try {
            if (section.type === 'text') {
                html += `
                    <div class="answer-section text-section">
                        ${section.title ? `<h3 class="section-title">${escapeHtml(section.title)}</h3>` : ''}
                        <div class="section-content">${formatTextContent(section.content)}</div>
                    </div>
                `;
            } else if (section.type === 'table') {
                html += renderTable(section);
            } else {
                // Handle unknown section types gracefully
                console.warn(`Unknown section type '${section.type}' at index ${index}`);
                if (section.content) {
                    html += `
                        <div class="answer-section text-section">
                            ${section.title ? `<h3 class="section-title">${escapeHtml(section.title)}</h3>` : ''}
                            <div class="section-content">${formatTextContent(section.content)}</div>
                        </div>
                    `;
                }
            }
        } catch (error) {
            console.error(`Error rendering section ${index}:`, error, section);
            // Render a fallback for this section
            html += `
                <div class="answer-section text-section">
                    <h3 class="section-title">Section ${index + 1}</h3>
                    <div class="section-content">
                        <p>Error rendering this section. Raw content:</p>
                        <pre>${escapeHtml(JSON.stringify(section, null, 2))}</pre>
                    </div>
                </div>
            `;
        }
    });

    return html;
}

// Format text content (preserve paragraphs and line breaks)
function formatTextContent(content) {
    if (!content) return '';
    
    // Escape HTML
    const escaped = escapeHtml(content);
    
    // Split into paragraphs and format
    const paragraphs = escaped.split('\n\n').filter(p => p.trim());
    
    if (paragraphs.length === 0) {
        return escaped.replace(/\n/g, '<br>');
    }
    
    return paragraphs.map(para => {
        return `<p>${para.replace(/\n/g, '<br>')}</p>`;
    }).join('');
}

// Render table section
function renderTable(section) {
    if (!section.columns || !section.rows) {
        return '<p>Invalid table format</p>';
    }

    let html = `<div class="answer-section table-section">`;
    
    if (section.title) {
        html += `<h3 class="section-title">${escapeHtml(section.title)}</h3>`;
    }

    html += '<div class="table-wrapper"><table class="data-table">';
    
    // Table header
    html += '<thead><tr>';
    section.columns.forEach(col => {
        html += `<th>${escapeHtml(col)}</th>`;
    });
    html += '</tr></thead>';

    // Table body
    html += '<tbody>';
    section.rows.forEach(row => {
        html += '<tr>';
        row.forEach(cell => {
            html += `<td>${escapeHtml(String(cell))}</td>`;
        });
        html += '</tr>';
    });
    html += '</tbody>';

    html += '</table></div></div>';

    return html;
}

// Helper function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================================
// Document Intelligence & File Handling Helpers
// ============================================================================

const ALLOWED_EXTENSIONS = ['pdf', 'png', 'jpg', 'jpeg', 'webp', 'docx', 'txt'];
const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024; // 50MB

function showInputError(message) {
    if (!inputErrorBanner || !inputErrorText) return;
    inputErrorText.textContent = message;
    inputErrorBanner.style.display = 'flex';
}

function hideInputError() {
    if (inputErrorBanner) {
        inputErrorBanner.style.display = 'none';
    }
}

function showUploadProgress(percent, statusText) {
    if (!uploadProgressContainer) return;
    uploadProgressContainer.style.display = 'block';
    if (progressBarFill) progressBarFill.style.width = `${percent}%`;
    if (progressStatusText) progressStatusText.textContent = statusText;
}

function hideUploadProgress() {
    if (!uploadProgressContainer) return;
    uploadProgressContainer.style.display = 'none';
    if (progressBarFill) progressBarFill.style.width = '0%';
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    if (ext === 'pdf') return '📄';
    if (['png', 'jpg', 'jpeg', 'webp'].includes(ext)) return '🖼️';
    if (ext === 'docx') return '📝';
    return '📄';
}

// File handling with validation
function handleFileSelection(event) {
    const files = Array.from(event.target.files);
    if (!files || files.length === 0) return;

    hideInputError();
    const validFiles = [];

    for (const file of files) {
        const ext = file.name.split('.').pop().toLowerCase();

        // 1. Format validation
        if (!ALLOWED_EXTENSIONS.includes(ext)) {
            showInputError(`File "${file.name}" has an unsupported format (.${ext}). Supported: PDF, PNG, JPG, JPEG, WEBP.`);
            fileInput.value = '';
            return;
        }

        // 2. Size validation
        if (file.size > MAX_FILE_SIZE_BYTES) {
            showInputError(`File "${file.name}" (${formatBytes(file.size)}) exceeds the maximum allowed limit of 50MB.`);
            fileInput.value = '';
            return;
        }

        validFiles.push(file);
    }

    uploadedFiles = [...uploadedFiles, ...validFiles];
    renderAttachmentChips();
    updateFileCount();
    toggleSendButton();
    fileInput.value = ''; // Reset input
}

function renderAttachmentChips() {
    if (!attachmentPreviewTray) return;

    if (uploadedFiles.length === 0) {
        attachmentPreviewTray.style.display = 'none';
        attachmentPreviewTray.innerHTML = '';
        return;
    }

    attachmentPreviewTray.style.display = 'flex';
    attachmentPreviewTray.innerHTML = uploadedFiles.map((file, idx) => `
        <div class="attachment-chip" title="${escapeHtml(file.name)}">
            <span class="chip-icon">${getFileIcon(file.name)}</span>
            <span class="chip-name">${escapeHtml(file.name)}</span>
            <span class="chip-size">(${formatBytes(file.size)})</span>
            <button type="button" class="chip-remove-btn" onclick="removeAttachment(${idx})" title="Remove file">&times;</button>
        </div>
    `).join('');
}

window.removeAttachment = function(index) {
    if (index >= 0 && index < uploadedFiles.length) {
        uploadedFiles.splice(index, 1);
        renderAttachmentChips();
        updateFileCount();
        toggleSendButton();
        if (uploadedFiles.length === 0) {
            hideInputError();
        }
    }
};

function updateFileCount() {
    if (!fileCount) return;
    if (uploadedFiles.length > 0) {
        fileCount.textContent = `📎 ${uploadedFiles.length} file${uploadedFiles.length > 1 ? 's' : ''} attached`;
        fileCount.style.display = 'block';
    } else {
        fileCount.style.display = 'none';
    }
}

// Active document context management per conversation
function getActiveSessionDoc(chatId) {
    if (!chatId) return null;
    try {
        const stored = localStorage.getItem('irium_active_docs');
        if (!stored) return null;
        const map = JSON.parse(stored);
        return map[chatId] || null;
    } catch {
        return null;
    }
}

function saveActiveSessionDoc(chatId, docData) {
    if (!chatId) return;
    try {
        const stored = localStorage.getItem('irium_active_docs');
        const map = stored ? JSON.parse(stored) : {};
        map[chatId] = docData;
        localStorage.setItem('irium_active_docs', JSON.stringify(map));
    } catch (e) {
        console.warn('Could not save active doc context:', e);
    }
}

function removeActiveSessionDoc(chatId) {
    if (!chatId) return;
    try {
        const stored = localStorage.getItem('irium_active_docs');
        if (stored) {
            const map = JSON.parse(stored);
            delete map[chatId];
            localStorage.setItem('irium_active_docs', JSON.stringify(map));
        }
    } catch (e) {}
}

function updateActiveDocBanner() {
    if (!activeDocBanner) return;
    const activeDoc = getActiveSessionDoc(currentChatId);
    if (activeDoc && activeDoc.filename) {
        if (activeDocName) activeDocName.textContent = activeDoc.filename;
        if (activeDocPages) {
            activeDocPages.textContent = activeDoc.pageCount > 1 ? `${activeDoc.pageCount} pages` : '1 page';
            activeDocPages.style.display = 'inline-block';
        }
        activeDocBanner.style.display = 'flex';
    } else {
        activeDocBanner.style.display = 'none';
    }
}

async function detachCurrentDocument() {
    if (!currentChatId) return;
    try {
        await fetch(apiUrl(`/api/documents/session/${currentChatId}`), {
            method: 'DELETE',
            headers: authHeaders()
        }).catch(() => {});
    } catch {}

    removeActiveSessionDoc(currentChatId);
    updateActiveDocBanner();
    addMessage('assistant', '📄 Document detached from this conversation. Subsequent questions will use general financial research mode.');
}

// Chat history management
function loadChatHistory() {
    const stored = localStorage.getItem('irium_chat_history');
    if (!stored) return;

    try {
        const parsedHistory = JSON.parse(stored);
        chatHistory = Array.isArray(parsedHistory) ? parsedHistory : [];
        renderChatHistory();
    } catch (error) {
        console.warn('Unable to load saved chat history:', error);
        localStorage.removeItem('irium_chat_history');
    }
}

function saveChatHistory(query) {
    const chat = {
        id: currentChatId || generateChatId(),
        query: query.substring(0, 50) + (query.length > 50 ? '...' : ''),
        timestamp: Date.now(),
        messages: [] // Will be populated when loading
    };

    chatHistory = [chat, ...chatHistory.filter(c => c.id !== chat.id)].slice(0, 50);
    localStorage.setItem('irium_chat_history', JSON.stringify(chatHistory));
    renderChatHistory();
    
    // Save messages for this chat
    saveCurrentChatMessages();
}

// Save current chat messages
function saveCurrentChatMessages() {
    if (!currentChatId) return;
    
    const messages = [];
    messagesContainer.querySelectorAll('.message').forEach(msg => {
        const role = msg.classList.contains('user') ? 'user' : 'assistant';
        const content = msg.querySelector('.message-content');
        if (content) {
            messages.push({
                role: role,
                content: content.innerHTML // Save HTML to preserve formatting
            });
        }
    });
    
    localStorage.setItem(`irium_chat_${currentChatId}`, JSON.stringify(messages));
}

// Load a specific chat by ID
function loadChatById(chatId) {
    // Save current chat before switching
    if (currentChatId) {
        saveCurrentChatMessages();
    }
    
    currentChatId = chatId;
    
    // Clear current view
    messagesContainer.innerHTML = '';
    uploadedFiles = [];
    renderAttachmentChips();
    hideInputError();
    hideUploadProgress();
    updateActiveDocBanner();
    messageInput.value = '';
    autoResizeTextarea();
    setProcessingState(false);
    updateFileCount();
    
    // Load messages for this chat
    const storedMessages = localStorage.getItem(`irium_chat_${chatId}`);
    if (storedMessages) {
        try {
            const messages = JSON.parse(storedMessages);
            if (messages.length > 0) {
                welcomeScreen.style.display = 'none';
                messages.forEach(msg => {
                    const messageDiv = document.createElement('div');
                    messageDiv.className = `message ${msg.role}`;
                    
                    if (msg.role === 'user') {
                        messageDiv.innerHTML = `
                            <div class="message-header">
                                <div class="message-avatar">You</div>
                            </div>
                            <div class="message-content">${msg.content}</div>
                        `;
                    } else {
                        let renderedContent = msg.content;
                        if (typeof renderedContent === 'string' && !renderedContent.includes('markdown-content')) {
                            const tempDiv = document.createElement('div');
                            tempDiv.innerHTML = renderedContent;
                            const rawText = tempDiv.innerText || tempDiv.textContent;
                            if (rawText && (rawText.includes('#') || rawText.includes('|') || rawText.includes('**') || rawText.includes('```'))) {
                                renderedContent = formatMarkdown(rawText);
                            } else {
                                renderedContent = `<div class="markdown-content">${renderedContent}</div>`;
                            }
                        }
                        messageDiv.innerHTML = `
                            <div class="message-header">
                                <div class="message-avatar">I</div>
                                <div class="message-author">Irium</div>
                            </div>
                            <div class="message-content">${renderedContent}</div>
                        `;
                    }
                    
                    messagesContainer.appendChild(messageDiv);
                });
                scrollToBottom();
            } else {
                welcomeScreen.style.display = 'flex';
            }
        } catch (error) {
            console.error('Failed to load chat messages:', error);
            welcomeScreen.style.display = 'flex';
        }
    } else {
        welcomeScreen.style.display = 'flex';
    }
    
    // Update active state in sidebar
    renderChatHistory();
    
    // Focus input
    messageInput.focus();
}

function renderChatHistory() {
    const now = Date.now();
    const oneDay = 24 * 60 * 60 * 1000;
    const oneWeek = 7 * oneDay;

    const today = chatHistory.filter(c => now - c.timestamp < oneDay);
    const yesterday = chatHistory.filter(c => {
        const diff = now - c.timestamp;
        return diff >= oneDay && diff < 2 * oneDay;
    });
    const week = chatHistory.filter(c => {
        const diff = now - c.timestamp;
        return diff >= 2 * oneDay && diff < oneWeek;
    });

    renderHistorySection('todayChats', today);
    renderHistorySection('yesterdayChats', yesterday);
    renderHistorySection('weekChats', week);
}

function renderHistorySection(containerId, chats) {
    const container = document.getElementById(containerId);
    if (!chats || chats.length === 0) {
        container.innerHTML = '<div style="padding: 8px 12px; color: var(--text-tertiary); font-size: 13px;">No chats</div>';
        return;
    }

    container.innerHTML = chats.map(chat => `
        <div class="history-item ${chat.id === currentChatId ? 'active' : ''}" data-chat-id="${chat.id}">
            ${escapeHtml(chat.query)}
        </div>
    `).join('');
    
    // Add click event listeners to history items
    container.querySelectorAll('.history-item').forEach(item => {
        item.addEventListener('click', () => {
            const chatId = item.getAttribute('data-chat-id');
            loadChatById(chatId);
        });
    });
}

// Utility functions
function generateChatId() {
    return 'chat_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

function generateMessageId() {
    return 'msg_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initial state
if (!currentChatId) {
    currentChatId = generateChatId();
}
