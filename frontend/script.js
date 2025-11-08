// API base URL - use relative path to work from any host
const API_URL = '/api';

// Global state
let currentSessionId = null;
let availableModels = [];
let currentModel = null;

// DOM elements
let chatMessages, chatInput, sendButton, totalCourses, courseTitles, modelSelect, modelContext;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Get DOM elements after page loads
    chatMessages = document.getElementById('chatMessages');
    chatInput = document.getElementById('chatInput');
    sendButton = document.getElementById('sendButton');
    totalCourses = document.getElementById('totalCourses');
    courseTitles = document.getElementById('courseTitles');
    modelSelect = document.getElementById('modelSelect');
    modelContext = document.getElementById('modelContext');

    setupEventListeners();
    createNewSession();
    loadCourseStats();
    loadAvailableModels();
});

// Event Listeners
function setupEventListeners() {
    // Chat functionality
    sendButton.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
    
    
    // Suggested questions
    document.querySelectorAll('.suggested-item').forEach(button => {
        button.addEventListener('click', (e) => {
            const question = e.target.getAttribute('data-question');
            chatInput.value = question;
            sendMessage();
        });
    });

    // Model selector
    if (modelSelect) {
        modelSelect.addEventListener('change', handleModelChange);
    }
}


// Chat Functions
async function sendMessage() {
    const query = chatInput.value.trim();
    if (!query) return;

    // Disable input
    chatInput.value = '';
    chatInput.disabled = true;
    sendButton.disabled = true;

    // Add user message
    addMessage(query, 'user');

    // Add loading message - create a unique container for it
    const loadingMessage = createLoadingMessage();
    chatMessages.appendChild(loadingMessage);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
        const response = await fetch(`${API_URL}/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: query,
                session_id: currentSessionId
            })
        });

        if (!response.ok) throw new Error('Query failed');

        const data = await response.json();
        
        // Update session ID if new
        if (!currentSessionId) {
            currentSessionId = data.session_id;
        }

        // Replace loading message with response
        loadingMessage.remove();
        addMessage(data.answer, 'assistant', data.sources);

    } catch (error) {
        // Replace loading message with error
        loadingMessage.remove();
        addMessage(`Error: ${error.message}`, 'assistant');
    } finally {
        chatInput.disabled = false;
        sendButton.disabled = false;
        chatInput.focus();
    }
}

function createLoadingMessage() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="loading">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    return messageDiv;
}

function addMessage(content, type, sources = null, isWelcome = false) {
    const messageId = Date.now();
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}${isWelcome ? ' welcome-message' : ''}`;
    messageDiv.id = `message-${messageId}`;

    // Convert markdown to HTML for assistant messages
    const displayContent = type === 'assistant' ? marked.parse(content) : escapeHtml(content);

    let html = `<div class="message-content">${displayContent}</div>`;

    if (sources && sources.length > 0) {
        // Format sources with clickable links
        const formattedSources = sources.map(source => {
            if (source.url) {
                // Create clickable link that opens in new tab
                return `<a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.label)}</a>`;
            } else {
                // No URL - just show the label
                return escapeHtml(source.label);
            }
        });

        html += `
            <details class="sources-collapsible">
                <summary class="sources-header">Sources</summary>
                <div class="sources-content">${formattedSources.join(', ')}</div>
            </details>
        `;
    }

    messageDiv.innerHTML = html;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    return messageId;
}

// Helper function to escape HTML for user messages
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Removed removeMessage function - no longer needed since we handle loading differently

async function createNewSession() {
    currentSessionId = null;
    chatMessages.innerHTML = '';
    addMessage('Welcome to the Course Materials Assistant! I can help you with questions about courses, lessons and specific content. What would you like to know?', 'assistant', null, true);
}

// Load course statistics
async function loadCourseStats() {
    try {
        console.log('Loading course stats...');
        const response = await fetch(`${API_URL}/courses`);
        if (!response.ok) throw new Error('Failed to load course stats');

        const data = await response.json();
        console.log('Course data received:', data);

        // Update stats in UI
        if (totalCourses) {
            totalCourses.textContent = data.total_courses;
        }

        // Update course titles
        if (courseTitles) {
            if (data.course_titles && data.course_titles.length > 0) {
                courseTitles.innerHTML = data.course_titles
                    .map(title => `<div class="course-title-item">${title}</div>`)
                    .join('');
            } else {
                courseTitles.innerHTML = '<span class="no-courses">No courses available</span>';
            }
        }

    } catch (error) {
        console.error('Error loading course stats:', error);
        // Set default values on error
        if (totalCourses) {
            totalCourses.textContent = '0';
        }
        if (courseTitles) {
            courseTitles.innerHTML = '<span class="error">Failed to load courses</span>';
        }
    }
}

// Load available models
async function loadAvailableModels() {
    try {
        console.log('Loading available models...');
        const response = await fetch(`${API_URL}/models`);
        if (!response.ok) throw new Error('Failed to load models');

        const data = await response.json();
        console.log('Models data received:', data);

        availableModels = data.available_models;
        currentModel = data.current_model;

        // Populate model selector
        if (modelSelect) {
            modelSelect.innerHTML = availableModels.map(model => `
                <option value="${model.id}" ${model.id === currentModel ? 'selected' : ''}>
                    ${model.name}
                </option>
            `).join('');

            // Update context display
            updateModelContext();
        }

    } catch (error) {
        console.error('Error loading models:', error);
        if (modelSelect) {
            modelSelect.innerHTML = '<option value="">Error loading models</option>';
        }
    }
}

// Update model context display
function updateModelContext() {
    if (!modelContext || !currentModel) return;

    const model = availableModels.find(m => m.id === currentModel);
    if (model) {
        const contextK = Math.round(model.context / 1000);
        modelContext.textContent = `${contextK}k context`;
        modelContext.title = model.description;
    }
}

// Handle model change
async function handleModelChange() {
    const selectedModel = modelSelect.value;
    if (!selectedModel || selectedModel === currentModel) return;

    // Disable selector during change
    modelSelect.disabled = true;

    try {
        const response = await fetch(`${API_URL}/models/select`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                model_id: selectedModel
            })
        });

        if (!response.ok) {
            throw new Error('Failed to switch model');
        }

        const data = await response.json();
        currentModel = selectedModel;
        updateModelContext();

        // Show notification
        showNotification(data.message, 'success');

    } catch (error) {
        console.error('Error switching model:', error);
        // Revert selection
        modelSelect.value = currentModel;
        showNotification('Failed to switch model. Using fallback.', 'error');
    } finally {
        modelSelect.disabled = false;
    }
}

// Show notification
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;

    // Add to body
    document.body.appendChild(notification);

    // Trigger animation
    setTimeout(() => notification.classList.add('show'), 10);

    // Remove after 3 seconds
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}