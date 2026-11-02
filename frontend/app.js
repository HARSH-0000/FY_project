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

document.addEventListener('DOMContentLoaded', () => {
    loadChatHistory();
    setupEventListeners();
    autoResizeTextarea();
    restoreAuthSession();
    checkUrlPrompt();
    updateActiveDocBanner();
    toggleSendButton();
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

    // Input change and clipboard events
    ['input', 'change', 'paste', 'cut', 'keyup'].forEach(evt => {
        messageInput.addEventListener(evt, () => {
            autoResizeTextarea();
            toggleSendButton();
        });
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

// Check if query is about the active document or is a general question
function isDocumentQuery(query) {
    const q = query.trim().toLowerCase();
    
    // Explicit document references
    const documentKeywords = [
        'in the document', 'in the pdf', 'in the file', 'in the report',
        'according to the document', 'according to the pdf',
        'this document', 'this pdf', 'this file', 'this report',
        'uploaded document', 'uploaded file',
        'page ', 'the chart', 'the table', 'the figure', 'the graph',
        'summarize this', 'summarize the document'
    ];
    
    if (documentKeywords.some(kw => q.includes(kw))) {
        return true;
    }
    
    // General definitional questions (NOT document-related)
    const generalPatterns = [
        /^what\s+is\s+(a|an|the)\s+\w+\??$/i,
        /^define\s+\w+/i,
        /^explain\s+(what\s+is|the\s+concept)/i,
        /^how\s+(does|do|can|to)\s+\w+/i,
    ];
    
    if (generalPatterns.some(pattern => pattern.test(q))) {
        return false;  // General question, not document-specific
    }
    
    // Follow-up references might be document-related
    // Check last message for document context
    const followupWords = ['that', 'this', 'it', 'these', 'those'];
    if (followupWords.some(w => q.includes(w))) {
        const messages = messagesContainer.querySelectorAll('.message');
        if (messages.length > 0) {
            const lastMsg = messages[messages.length - 1];
            const lastContent = (lastMsg.querySelector('.message-content')?.textContent || '').toLowerCase();
            // If last message mentioned document/pages, likely a follow-up
            if (lastContent.includes('document') || lastContent.includes('page') || lastContent.includes('pdf')) {
                return true;
            }
        }
    }
    
    // Default: not a document query
    return false;
}

async function handleSendMessage() {
    const hasFiles = uploadedFiles.length > 0;
    if (sendBtn && sendBtn.disabled && !hasFiles) return;
    if (isProcessing) return;

    let message = messageInput.value.trim();
    const activeDoc = getActiveSessionDoc(currentChatId);

    if (!message && !hasFiles) return;

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
        } else if (activeDoc && isDocumentQuery(message)) {
            // Follow-up question ABOUT the document in this conversation
            await handleDocumentFollowUp(message);
        } else {
            // Standard financial research mode (even if doc exists but query is general)
            await handleResearch(message);
        }
    } catch (error) {
        console.error('handleSendMessage error:', error);
        const errorMessage = error.message || JSON.stringify(error);
        if (errorMessage.includes('rate_limit') || errorMessage.includes('429')) {
            showInputError('Rate limit encountered. System will automatically retry.');
        } else {
            showInputError(error.message || 'Failed to process request.');
        }
    } finally {
        // CRITICAL: Always reset processing state to prevent stuck UI
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
        if (sendBtn) {
            sendBtn.style.display = 'none';
            sendBtn.disabled = true;
        }
        if (stopBtn) {
            stopBtn.style.display = 'flex';
            stopBtn.disabled = false;
        }
        
        // Disable input
        if (inputWrapper) inputWrapper.classList.add('disabled');
        if (messageInput) messageInput.disabled = true;
        if (attachBtn) attachBtn.disabled = true;
    } else {
        // Hide stop button, show send button
        if (stopBtn) {
            stopBtn.style.display = 'none';
            stopBtn.disabled = true;
        }
        if (sendBtn) sendBtn.style.display = 'flex';
        
        // Enable input
        if (inputWrapper) inputWrapper.classList.remove('disabled');
        if (messageInput) messageInput.disabled = false;
        if (attachBtn) attachBtn.disabled = false;
        
        // Reset controller
        currentRequestController = null;
    }
    
    toggleSendButton();
}

// Handle stop generation
function handleStopGeneration() {
    if (stopBtn) {
        stopBtn.disabled = true;
    }
    if (currentRequestController) {
        currentRequestController.abort();
        currentRequestController = null;
    }
    hideUploadProgress();
    setProcessingState(false);
}

// Extract conversation turns for reference resolution
function getRecentConversationTurns(maxTurns = 6) {
    const turns = [];
    const messageElements = messagesContainer.querySelectorAll('.message');
    messageElements.forEach(el => {
        const isUser = el.classList.contains('user');
        const contentEl = el.querySelector('.message-content');
        if (contentEl) {
            // Extract text content, preserving important info but limiting length
            const text = contentEl.innerText || contentEl.textContent || '';
            if (text.trim()) {
                turns.push({
                    role: isUser ? 'user' : 'assistant',
                    content: text.slice(0, 500)  // Increased from 300 to 500 for better context
                });
            }
        }
    });
    // Return last N turns (user + assistant pairs)
    return turns.slice(-maxTurns);
}

// Helper function to add a loading message
function addLoadingMessage() {
    const loadingId = 'loading-' + Date.now();
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message assistant';
    loadingDiv.id = loadingId;
    
    loadingDiv.innerHTML = `
        <div class="message-header">
            <div class="message-avatar">I</div>
            <div class="message-author">Irium</div>
        </div>
        <div class="message-content">
            <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    
    messagesContainer.appendChild(loadingDiv);
    scrollToBottom();
    return loadingId;
}

// Helper function to remove loading message
function removeLoadingMessage(loadingId) {
    const loadingDiv = document.getElementById(loadingId);
    if (loadingDiv) {
        loadingDiv.remove();
    }
}

// Handle research request (non-streaming, simple and reliable)
async function handleResearch(query) {
    const loadingId = addLoadingMessage();
    currentRequestController = new AbortController();

    try {
        // Build request with conversation context
        const requestBody = {
            query: query,
            conversation_id: currentChatId,
            conversation_history: getRecentConversationTurns(6)
        };

        const response = await fetch(apiUrl('/api/research'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...authHeaders(),
            },
            body: JSON.stringify(requestBody),
            signal: currentRequestController.signal,
        });

        // Remove loading indicator
        removeLoadingMessage(loadingId);

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            
            // Handle structured error responses (e.g., INVALID_QUERY_DOMAIN)
            let errorMessage = '';
            if (errData.detail && typeof errData.detail === 'object') {
                // Structured error with message field
                errorMessage = errData.detail.message || errData.detail.error || 'An error occurred';
            } else if (typeof errData.detail === 'string') {
                // Simple string error
                errorMessage = errData.detail;
            } else {
                // Fallback
                errorMessage = `HTTP error! status: ${response.status}`;
            }
            
            throw new Error(errorMessage);
        }

        const data = await response.json();
        
        // Check for clarification
        if (data.requires_clarification) {
            const clarificationMsg = data.clarification_question || data.answer;
            addMessage('assistant', clarificationMsg);
            return;
        }

        // Check if this is a report response
        if (data.type === 'report') {
            addReportMessage(data);
            return;
        }

        // Build final content with answer, visualizations, and sources
        let answerContent = '';
        
        // Get answer
        const answer = data.answer || data.result?.answer || '';
        if (typeof answer === 'string') {
            answerContent = answer;
        } else if (typeof answer === 'object' && answer.summary) {
            answerContent = answer.summary;
        } else {
            answerContent = JSON.stringify(answer);
        }

        // Format the answer (markdown rendering)
        let finalContent = formatMarkdown(answerContent);

        // Append chart visualizations if available
        const visualizations = data.visualizations || data.result?.visualizations || [];
        if (Array.isArray(visualizations) && visualizations.length > 0 && typeof renderVisualizations === 'function') {
            finalContent += renderVisualizations(visualizations);
        }

        // Append sources if available (raw HTML, not markdown)
        const sources = data.sources || data.result?.sources || [];
        if (sources.length > 0) {
            let sourcesHtml = '<div class="sources">';
            sourcesHtml += '<div class="sources-title">Sources:</div>';
            sourcesHtml += '<div class="source-list">';
            sources.forEach((source) => {
                const sourceUrl = source.url || source.source_url || '#';
                const sourceTitle = source.title || source.source_title || source.name || source.source_name || sourceUrl;
                sourcesHtml += `
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
            sourcesHtml += '</div></div>';
            finalContent += sourcesHtml;
        }

        // Add the complete message (skip formatMarkdown in addMessage since we already formatted)
        addMessageRaw('assistant', finalContent);

        // Auto-save messages to history
        if (currentChatId) {
            saveCurrentChatMessages();
        }

    } catch (error) {
        // Remove loading indicator on error
        removeLoadingMessage(loadingId);
        
        console.error('Research request error:', error);
        if (error.name !== 'AbortError') {
            const errorMessage = error.message || 'Error processing request.';
            
            // Check if this is a domain validation error
            const isDomainError = errorMessage.includes('outside IRIUM\'s scope') || 
                                  errorMessage.includes('specializes in');
            
            // Create an enhanced, user-friendly error message display
            const errorHtml = `
                <div class="error-message-card" style="
                    background: linear-gradient(135deg, #2a1a1a 0%, #1a1414 100%);
                    border: 1px solid rgba(255, 100, 100, 0.3);
                    border-left: 4px solid #ff6464;
                    border-radius: 16px;
                    padding: 24px;
                    margin: 16px 0;
                    box-shadow: 0 4px 20px rgba(255, 100, 100, 0.1);
                    animation: slideIn 0.3s ease-out;
                ">
                    <style>
                        @keyframes slideIn {
                            from {
                                opacity: 0;
                                transform: translateY(-10px);
                            }
                            to {
                                opacity: 1;
                                transform: translateY(0);
                            }
                        }
                        .error-icon {
                            animation: pulse 2s ease-in-out infinite;
                        }
                        @keyframes pulse {
                            0%, 100% { transform: scale(1); }
                            50% { transform: scale(1.1); }
                        }
                        .example-button {
                            background: linear-gradient(135deg, #4a4a4a 0%, #333 100%);
                            border: 1px solid rgba(255, 255, 255, 0.1);
                            border-radius: 8px;
                            padding: 8px 16px;
                            margin: 4px;
                            cursor: pointer;
                            transition: all 0.2s ease;
                            display: inline-block;
                            font-size: 13px;
                            color: var(--text-primary);
                        }
                        .example-button:hover {
                            background: linear-gradient(135deg, #5a5a5a 0%, #444 100%);
                            border-color: rgba(100, 200, 255, 0.5);
                            transform: translateY(-2px);
                            box-shadow: 0 4px 12px rgba(100, 200, 255, 0.2);
                        }
                        .capability-item {
                            display: flex;
                            align-items: center;
                            gap: 12px;
                            padding: 8px 0;
                            opacity: 0;
                            animation: fadeInItem 0.3s ease-out forwards;
                        }
                        .capability-item:nth-child(1) { animation-delay: 0.1s; }
                        .capability-item:nth-child(2) { animation-delay: 0.15s; }
                        .capability-item:nth-child(3) { animation-delay: 0.2s; }
                        .capability-item:nth-child(4) { animation-delay: 0.25s; }
                        .capability-item:nth-child(5) { animation-delay: 0.3s; }
                        .capability-item:nth-child(6) { animation-delay: 0.35s; }
                        @keyframes fadeInItem {
                            from {
                                opacity: 0;
                                transform: translateX(-10px);
                            }
                            to {
                                opacity: 1;
                                transform: translateX(0);
                            }
                        }
                    </style>
                    
                    <div style="display: flex; align-items: flex-start; gap: 16px;">
                        <div class="error-icon" style="
                            font-size: 32px;
                            min-width: 32px;
                            filter: drop-shadow(0 2px 8px rgba(255, 100, 100, 0.3));
                        ">⚠</div>
                        
                        <div style="flex: 1;">
                            <div style="
                                font-weight: 700;
                                color: #ff8888;
                                margin-bottom: 16px;
                                font-size: 18px;
                                letter-spacing: 0.5px;
                            ">Query Not Allowed</div>
                            
                            <div style="
                                color: var(--text-primary);
                                line-height: 1.7;
                                white-space: pre-wrap;
                                margin-bottom: 20px;
                                padding: 16px;
                                background: rgba(255, 255, 255, 0.03);
                                border-radius: 8px;
                                border-left: 2px solid rgba(255, 100, 100, 0.3);
                            ">${escapeHtml(errorMessage)}</div>
                            
                            ${isDomainError ? `
                                <div style="
                                    margin-top: 24px;
                                    padding-top: 20px;
                                    border-top: 1px solid rgba(255, 255, 255, 0.1);
                                ">
                                    <div style="
                                        font-weight: 600;
                                        color: #88ccff;
                                        margin-bottom: 16px;
                                        font-size: 15px;
                                        display: flex;
                                        align-items: center;
                                        gap: 8px;
                                    ">
                                        <span style="font-size: 18px;">→</span>
                                        <span>Try asking about these topics instead:</span>
                                    </div>
                                    
                                    <div style="display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 20px;">
                                        <button class="example-button" onclick="window.tryExampleQuery('What is GDP and how is it calculated?')">
                                            What is GDP?
                                        </button>
                                        <button class="example-button" onclick="window.tryExampleQuery('Explain inflation and its impact on economy')">
                                            Inflation Impact
                                        </button>
                                        <button class="example-button" onclick="window.tryExampleQuery('What are stock market indices?')">
                                            Stock Indices
                                        </button>
                                        <button class="example-button" onclick="window.tryExampleQuery('Compare HDFC and ICICI Bank performance')">
                                            Bank Comparison
                                        </button>
                                        <button class="example-button" onclick="window.tryExampleQuery('Explain cryptocurrency and blockchain in finance')">
                                            Crypto Finance
                                        </button>
                                    </div>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
            
            addMessageRaw('assistant', errorHtml);
            throw error; // Re-throw to be caught by handleSendMessage
        } else {
            addMessage('assistant', '<p style="color: var(--text-tertiary); font-style: italic;">Generation stopped by user.</p>');
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

// Add message with raw HTML content (no markdown processing)
function addMessageRaw(role, htmlContent) {
    const messageId = generateMessageId();
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    messageDiv.id = messageId;

    const avatar = role === 'user' ? 'You' : 'AI';
    const avatarInitial = role === 'user' ? 'Y' : 'I';

    messageDiv.innerHTML = `
        <div class="message-header">
            <div class="message-avatar">${avatarInitial}</div>
            <div class="message-author">${avatar}</div>
        </div>
        <div class="message-content">
            ${htmlContent}
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

    // Handle structured answer format - format markdown separately
    if (data.answer && typeof data.answer === 'object' && data.answer.sections) {
        content = formatMarkdown(data.answer);
    } else if (typeof data.answer === 'string') {
        content = formatMarkdown(data.answer);
    } else {
        content = '<p>Invalid response format</p>';
    }

    // Render chart visualizations if available
    const visualizations = data.visualizations || (data.answer && data.answer.visualizations) || [];
    if (Array.isArray(visualizations) && visualizations.length > 0 && typeof renderVisualizations === 'function') {
        content += renderVisualizations(visualizations);
    }

    // Add sources if available - append as raw HTML (no markdown escaping)
    const sources = data.sources || (data.answer && data.answer.sources) || [];
    if (sources.length > 0) {
        let sourcesHtml = '<div class="sources">';
        sourcesHtml += '<div class="sources-title">Sources:</div>';
        sourcesHtml += '<div class="source-list">';
        sources.forEach((source) => {
            const sourceUrl = source.url || source.source_url || '#';
            const sourceTitle = source.title || source.source_title || source.name || source.source_name || sourceUrl;
            sourcesHtml += `
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
        sourcesHtml += '</div></div>';
        content += sourcesHtml;
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

// Add report message with download card
function addReportMessage(data) {
    const messageId = generateMessageId();
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.id = messageId;

    // Format: PDF • 3 pages or DOCX • ? pages
    const formatUpper = data.format.toUpperCase();
    const pagesInfo = data.pages ? `${data.pages} page${data.pages !== 1 ? 's' : ''}` : '? pages';
    
    const content = `
        <div class="report-card">
            <div class="report-icon">${data.format === 'pdf' ? '📄' : '📝'}</div>
            <div class="report-info">
                <h3 class="report-title">${escapeHtml(data.title || 'Report')}</h3>
                <p class="report-meta">${formatUpper} • ${pagesInfo}</p>
                ${data.message ? `<p class="report-message">${escapeHtml(data.message)}</p>` : ''}
            </div>
            <a href="${apiUrl(data.download_url)}" 
               download="${escapeHtml(data.filename)}"
               class="download-btn">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <polyline points="7 10 12 15 17 10" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <line x1="12" y1="15" x2="12" y2="3" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                Download ${formatUpper}
            </a>
        </div>
    `;

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

    // Render chart visualizations if available in document responses
    const docVisualizations = data.visualizations || (data.answer && data.answer.visualizations) || [];
    if (Array.isArray(docVisualizations) && docVisualizations.length > 0 && typeof renderVisualizations === 'function') {
        content += renderVisualizations(docVisualizations);
    }

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

// Add loading message with optional custom text
function addLoadingMessage(text = null) {
    const messageId = generateMessageId();
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.id = messageId;

    let contentHTML;
    if (text) {
        contentHTML = `
            <div class="stream-status">
                <div class="stream-status-text">${escapeHtml(text)}</div>
            </div>
        `;
    } else {
        contentHTML = `
            <div class="loading-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        `;
    }

    messageDiv.innerHTML = `
        <div class="message-header">
            <div class="message-avatar">I</div>
            <div class="message-author">Irium</div>
        </div>
        <div class="message-content">
            ${contentHTML}
        </div>
    `;

    messagesContainer.appendChild(messageDiv);
    scrollToBottom();

    return messageId;
}

// Update loading message with new text
function updateLoadingMessage(messageId, text) {
    const messageDiv = document.getElementById(messageId);
    if (!messageDiv) return;
    
    const contentDiv = messageDiv.querySelector('.message-content');
    if (!contentDiv) return;
    
    contentDiv.innerHTML = `
        <div class="stream-status">
            <div class="stream-status-text">${escapeHtml(text)}</div>
        </div>
    `;
    
    scrollToBottom();
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

// Math formula rendering helper (KaTeX with semantic HTML fallback)
function renderMathFormula(latex, isDisplay = true) {
    if (!latex) return '';
    let raw = latex.trim();
    
    // Strip surrounding brackets if present: [ ... ] or \[ ... \]
    if (raw.startsWith('\\[') && raw.endsWith('\\]')) {
        raw = raw.slice(2, -2).trim();
    } else if (raw.startsWith('$$') && raw.endsWith('$$')) {
        raw = raw.slice(2, -2).trim();
    } else if (raw.startsWith('[') && raw.endsWith(']')) {
        raw = raw.slice(1, -1).trim();
    }

    // Normalize common LLM dropped-underscore subscripts: \text{A}{\text{B}} or \text{A}{B} -> \text{A}_{\text{B}}
    raw = raw.replace(/(\\text\{[^{}]*\})\{(\s*\\text\{[^{}]*\}|[a-zA-Z0-9_\s]+)\}/g, '$1_{$2}');

    // Try KaTeX if available on window
    if (typeof katex !== 'undefined' && typeof katex.renderToString === 'function') {
        try {
            return katex.renderToString(raw, {
                displayMode: isDisplay,
                throwOnError: false
            });
        } catch (e) {
            console.warn('KaTeX rendering error, falling back to clean text math:', e);
        }
    }

    // High quality semantic fallback for mathematical & financial formulas
    let clean = raw;
    clean = clean.replace(/\\text\{([^{}]+)\}/g, '$1');
    clean = clean.replace(/_\{([^{}]+)\}/g, '<sub>$1</sub>');
    clean = clean.replace(/_([a-zA-Z0-9]+)/g, '<sub>$1</sub>');
    clean = clean.replace(/\^\{([^{}]+)\}/g, '<sup>$1</sup>');
    clean = clean.replace(/\^([a-zA-Z0-9]+)/g, '<sup>$1</sup>');
    clean = clean.replace(/\\times\b/g, ' × ');
    clean = clean.replace(/\\approx\b/g, ' ≈ ');
    clean = clean.replace(/\\cdot\b/g, ' · ');
    clean = clean.replace(/\\pm\b/g, ' ± ');
    clean = clean.replace(/\\Delta\b/g, 'Δ');
    clean = clean.replace(/\\le\b|\\leq\b/g, ' ≤ ');
    clean = clean.replace(/\\ge\b|\\geq\b/g, ' ≥ ');
    clean = clean.replace(/\\neq\b/g, ' ≠ ');
    clean = clean.replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, '($1 / $2)');
    clean = clean.replace(/[{}]/g, '');
    clean = clean.replace(/\\/g, '');

    const tagClass = isDisplay ? 'math-formula-card' : 'math-formula-inline';
    return `<div class="${tagClass}"><span class="math-formula-content">${clean}</span></div>`;
}

// Preprocess raw markdown text to normalize section headings, math blocks, and tables
function preprocessMarkdownAndMath(text) {
    if (!text || typeof text !== 'string') return { text: '', mathBlocks: [] };

    // 1. Normalize numbered section headings (e.g. "1.2 Impact on..." -> "### 1.2 Impact on...")
    text = text.replace(/(^|\n)(?:\s*)([0-9]+\.[0-9]+(?:\.[0-9]+)?\s+[A-Za-z].*?)(?=\n|$)/g, '$1### $2');

    // 2. Extract math blocks and replace with placeholders before marked.parse
    const mathBlocks = [];
    const displayMathRegex = /(?:\\\[\s*([\s\S]*?)\s*\\\]|\$\$\s*([\s\S]*?)\s*\$\$|(?:\n|^)\s*\[\s*\n+([\s\S]*?(?:\\text|\\times|\\approx|\\frac|=|\\cdot|\\Delta)[\s\S]*?)\n+\s*\](?=\n|$))/g;

    text = text.replace(displayMathRegex, (match, p1, p2, p3) => {
        const raw = (p1 || p2 || p3 || '').trim();
        const placeholder = `@@MATH_DISPLAY_BLOCK_${mathBlocks.length}@@`;
        mathBlocks.push(renderMathFormula(raw, true));
        return `\n\n${placeholder}\n\n`;
    });

    // 3. Balance incomplete markdown table rows (pad missing trailing cells with '—')
    const lines = text.split('\n');
    let inTable = false;
    let expectedCols = 0;
    const processedLines = [];

    for (let i = 0; i < lines.length; i++) {
        let line = lines[i];
        const trimmed = line.trim();
        if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
            const cells = trimmed.split('|').slice(1, -1);
            if (!inTable) {
                inTable = true;
                expectedCols = cells.length;
            } else if (trimmed.includes('---')) {
                // separator row
            } else {
                // data row
                if (cells.length < expectedCols) {
                    const diff = expectedCols - cells.length;
                    line = line.replace(/\|\s*$/, '') + ' | —'.repeat(diff) + ' |';
                }
            }
        } else {
            inTable = false;
            expectedCols = 0;
        }
        processedLines.push(line);
    }
    text = processedLines.join('\n');

    return { text, mathBlocks };
}

// Render markdown and structured answer format
function formatMarkdown(answer) {
    if (!answer) return '';

    // Check if answer is structured JSON format
    if (typeof answer === 'object' && answer.sections) {
        // Check if any section contains nested JSON in its content
        if (Array.isArray(answer.sections)) {
            for (let section of answer.sections) {
                if (section.content && typeof section.content === 'string') {
                    const content = section.content.trim();
                    if (content.startsWith('{') && content.includes('sections')) {
                        try {
                            const parsedContent = JSON.parse(content);
                            if (parsedContent.sections && Array.isArray(parsedContent.sections)) {
                                return `<div class="markdown-content">${renderStructuredAnswer(parsedContent)}</div>`;
                            }
                        } catch (e) {
                            // continue
                        }
                    }
                }
            }
        }
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
                return `<div class="markdown-content">${renderStructuredAnswer(parsedAnswer)}</div>`;
            }
        } catch (e) {
            // continue with regular markdown parsing
        }
    }

    const { text: preprocessed, mathBlocks } = preprocessMarkdownAndMath(answer);
    let parsedHtml = '';

    if (typeof marked !== 'undefined' && marked.parse) {
        try {
            marked.use({
                gfm: true,
                breaks: true,
                hooks: {
                    postprocess(html) {
                        return html.replace(/<table(\s*[^>]*)?>([\s\S]*?)<\/table>/gi, (match) => {
                            return `<div class="markdown-table-wrapper">${match}</div>`;
                        });
                    }
                }
            });

            parsedHtml = marked.parse(preprocessed);
        } catch (err) {
            console.error('Error in marked parser:', err);
            parsedHtml = fallbackMarkdownParse(preprocessed);
        }
    } else {
        parsedHtml = fallbackMarkdownParse(preprocessed);
    }

    // Restore math blocks safely
    mathBlocks.forEach((rendered, idx) => {
        parsedHtml = parsedHtml.replace(`<p>@@MATH_DISPLAY_BLOCK_${idx}@@</p>`, rendered)
                               .replace(`@@MATH_DISPLAY_BLOCK_${idx}@@`, rendered);
    });

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

    // Sanitize with DOMPurify if available, preserving math, table, and formatting markup
    if (typeof DOMPurify !== 'undefined' && DOMPurify.sanitize) {
        parsedHtml = DOMPurify.sanitize(parsedHtml, {
            ADD_ATTR: ['target', 'rel', 'class', 'style', 'xmlns', 'display', 'aria-hidden'],
            ADD_TAGS: [
                'span', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'div', 'input', 
                'sub', 'sup', 'math', 'annotation', 'semantics', 'mtext', 'mn', 'mo', 
                'mi', 'mspace', 'mover', 'munder', 'mrow', 'mfrac', 'msqrt', 'mroot', 
                'msub', 'msup', 'msubsup'
            ]
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
            } else if (section.type === 'chart' || section.type === 'visualization') {
                if (typeof renderSingleChart === 'function') {
                    html += renderSingleChart(section, index);
                }
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

// Format text content (run through full markdown formatting for rich typography and math)
function formatTextContent(content) {
    if (!content) return '';
    return formatMarkdown(content);
}

// Robust table cell value extractor supporting multiple naming patterns and synonyms
function getTableCellValue(row, colName, colIndex, allColumns) {
    if (row === null || row === undefined) return '';

    if (Array.isArray(row)) {
        if (colIndex < row.length && row[colIndex] !== undefined && row[colIndex] !== null) {
            return String(row[colIndex]);
        }
        return '';
    }

    if (typeof row === 'object') {
        // 1. Direct key match
        if (row[colName] !== undefined && row[colName] !== null) {
            return String(row[colName]);
        }

        // 2. Case-insensitive key match
        const colLower = colName.trim().toLowerCase();
        for (const [k, v] of Object.entries(row)) {
            if (k.trim().toLowerCase() === colLower && v !== undefined && v !== null) {
                return String(v);
            }
        }

        // 3. Normalized alphanumeric match
        const colNorm = colLower.replace(/[^a-z0-9]/g, '');
        for (const [k, v] of Object.entries(row)) {
            if (k.toLowerCase().replace(/[^a-z0-9]/g, '') === colNorm && v !== undefined && v !== null) {
                return String(v);
            }
        }

        // 4. Financial table synonym mapping
        const synonyms = {
            'takeaway': ['takeaway', 'key takeaway', 'point', 'finding', 'insight', 'aspect', 'observation', 'factor', 'event', 'summary'],
            'implication': ['implication', 'implications', 'impact', 'economic impact', 'financial impact', 'effect', 'consequence', 'outcome', 'result', 'detail', 'details', 'description', 'notes'],
            'metric': ['metric', 'indicator', 'kpi', 'measure', 'parameter', 'item'],
            'value': ['value', 'amount', 'figure', 'number', 'data', 'stat'],
            'period': ['period', 'year', 'quarter', 'date', 'timeline', 'timeframe', 'fy']
        };

        for (const [canonical, list] of Object.entries(synonyms)) {
            if (list.some(s => colLower.includes(s) || s.includes(colLower))) {
                for (const syn of list) {
                    for (const [k, v] of Object.entries(row)) {
                        const kLower = k.toLowerCase();
                        if ((kLower === syn || kLower.includes(syn)) && v !== undefined && v !== null && String(v).trim()) {
                            return String(v);
                        }
                    }
                }
            }
        }

        // 5. Positional fallback from object keys
        const keys = Object.keys(row);
        if (colIndex < keys.length && row[keys[colIndex]] !== undefined && row[keys[colIndex]] !== null) {
            return String(row[keys[colIndex]]);
        }
    }

    return String(row);
}

// Format individual table cell content with inline markdown and empty placeholder
function formatTableCell(value) {
    if (value === undefined || value === null || String(value).trim() === '') {
        return '<span class="empty-cell-dash">—</span>';
    }

    const str = String(value).trim();

    if (typeof marked !== 'undefined' && typeof marked.parseInline === 'function') {
        try {
            return marked.parseInline(str);
        } catch (e) {
            // fallback
        }
    }

    return escapeHtml(str)
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>');
}

// Render table section with full column alignment, synonym fallback, and inline formatting
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

        section.columns.forEach((colName, colIdx) => {
            const rawValue = getTableCellValue(row, colName, colIdx, section.columns);
            const formattedCell = formatTableCell(rawValue);
            html += `<td>${formattedCell}</td>`;
        });

        html += '</tr>';
    });
    html += '</tbody>';

    html += '</table></div>';
    html += '</div>';

    return html;
}

// Helper function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Helper function to try example queries from error message
window.tryExampleQuery = function(exampleQuery) {
    if (!messageInput) return;
    
    // Set the query in the input
    messageInput.value = exampleQuery;
    autoResizeTextarea();
    toggleSendButton();
    
    // Focus the input
    messageInput.focus();
    
    // Optionally, auto-submit after a brief moment
    setTimeout(() => {
        if (messageInput.value === exampleQuery && !isProcessing) {
            handleSendMessage();
        }
    }, 500);
};

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


// ==========================================
// FLOATING SCROLL-TO-BOTTOM BUTTON
// ==========================================

const scrollToBottomBtn = document.getElementById('scrollToBottomBtn');
const chatContainer = document.querySelector('.chat-container'); // The actual scrollable container
let isUserScrolling = false;
let scrollTimeout = null;

/**
 * Check if user is at the bottom of the chat container
 */
function isAtBottom() {
    if (!chatContainer) return true;
    
    const threshold = 150; // pixels from bottom
    const scrollTop = chatContainer.scrollTop;
    const scrollHeight = chatContainer.scrollHeight;
    const clientHeight = chatContainer.clientHeight;
    
    return (scrollHeight - scrollTop - clientHeight) < threshold;
}

/**
 * Scroll to the bottom of messages smoothly
 */
function scrollToBottom(behavior = 'smooth') {
    if (chatContainer) {
        chatContainer.scrollTo({
            top: chatContainer.scrollHeight,
            behavior: behavior
        });
    }
}

/**
 * Update the visibility of the scroll-to-bottom button
 */
function updateScrollButton() {
    if (!scrollToBottomBtn) return;
    
    const atBottom = isAtBottom();
    
    if (atBottom) {
        scrollToBottomBtn.classList.remove('visible');
    } else {
        scrollToBottomBtn.classList.add('visible');
    }
}

/**
 * Handle scroll events on chat container
 */
function handleMessagesScroll() {
    // Clear any existing timeout
    if (scrollTimeout) {
        clearTimeout(scrollTimeout);
    }
    
    // Mark that user is scrolling
    isUserScrolling = true;
    
    // Update button visibility immediately
    updateScrollButton();
    
    // Reset the scrolling flag after a delay
    scrollTimeout = setTimeout(() => {
        isUserScrolling = false;
    }, 150);
}

/**
 * Auto-scroll when AI generates a response (only if user is already at bottom)
 */
function autoScrollIfAtBottom() {
    if (isAtBottom() && !isUserScrolling) {
        scrollToBottom('smooth');
    }
}

/**
 * Force scroll to bottom (used when sending a message)
 */
function forceScrollToBottom() {
    scrollToBottom('smooth');
}

// Event Listeners for Scroll Button
if (scrollToBottomBtn) {
    scrollToBottomBtn.addEventListener('click', () => {
        forceScrollToBottom();
        scrollToBottomBtn.classList.remove('visible');
    });
}

// Scroll event listener on chat container (the actual scrollable element)
if (chatContainer) {
    chatContainer.addEventListener('scroll', handleMessagesScroll);
    
    // Initial check
    updateScrollButton();
}

// Observe DOM changes in messages container (for auto-scroll during AI response)
if (messagesContainer) {
    const observer = new MutationObserver((mutations) => {
        // Only auto-scroll if user was already at the bottom
        autoScrollIfAtBottom();
        
        // Update button visibility
        updateScrollButton();
    });
    
    observer.observe(messagesContainer, {
        childList: true,
        subtree: true,
        characterData: true
    });
}

/**
 * Enhanced sendMessage function with scroll behavior
 * This integrates with the existing sendMessage function
 */
const originalSendMessage = window.sendMessage;
if (typeof originalSendMessage === 'function') {
    window.sendMessage = async function(...args) {
        // Call the original function
        const result = await originalSendMessage.apply(this, args);
        
        // Force scroll to bottom when user sends a message
        setTimeout(() => {
            forceScrollToBottom();
        }, 100);
        
        return result;
    };
}

// Export functions for use in other parts of the app
window.scrollToBottom = scrollToBottom;
window.forceScrollToBottom = forceScrollToBottom;
window.autoScrollIfAtBottom = autoScrollIfAtBottom;
window.updateScrollButton = updateScrollButton;

console.log('✅ Scroll-to-bottom button initialized');
