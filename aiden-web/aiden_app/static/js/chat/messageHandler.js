import { updateUserDocuments } from '../profile/documentHandler.js';
import { updateCounters } from '../utils/counters.js';
import { updateProfiles } from '../profile/profileHandler.js';
import { formatJson } from '../utils/jsonFormatter.js';


export function appendMessage(role, message, isMarkdown = false) {
    let chatMessage;
    if (role == 'tool') {
        let name = message.name;
        let args = message.arguments;
        let formattedJson = formatJson(message.result);
        chatMessage = $('<div>').addClass('message-container').addClass('json-message').html(`<p>${name} ${args}</p>${formattedJson}`);
    } else {
        if (isMarkdown) {
            chatMessage = $('<div>').addClass('message-container').html(marked.parse(message));
        } else {
            chatMessage = $('<div>').addClass('message-container').text(message);
        }
    }
    let image = $('<img>').attr('src', role === 'assistant' ? "static/images/dog.png" : (role === 'tool' ? "static/images/tools.png" : "static/images/user-image.png"));
    image.addClass('chat-icon');
    chatMessage.prepend(image);
    $('#chat-window').append($(chatMessage));
}


export function handleResponse(data) {
    let message_role = data.role;
    let message_content = data.content;
    if (data.is_last) {
        $('#send-button').css('display', 'inline-block');
    }
    if (data.documents) {
        updateUserDocuments(data.documents);
    }
    if (message_role == 'assistant') {
        appendMessage(message_role, message_content, true);
        let tokens_used = data.tokens_used;
        updateCounters(tokens_used);
    } else if (message_role == 'tool') {
        message_content = JSON.parse(message_content);
        if (message_content.name == 'talk') {
            appendMessage('assistant', message_content.result, true);
        } else {
            appendMessage(message_role, message_content, false);
        }
    } else if (message_role == 'get_profiles') {
        updateProfiles(message_content);
    }
}
