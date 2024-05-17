import { sendChatRequest } from './chat/chatHandler.js';
import { appendMessage } from './chat/messageHandler.js';
import { createNewProfileContainer } from './profile/profileHandler.js';
import { showBigImage } from './profile/documentHandler.js';



$(document).ready(function () {
    sendChatRequest('/api/get_profiles', {});
});

$('#chat-form').on('submit', function (e) {
    e.preventDefault();
    let user_input = $('#user_input').val();
    $('#user_input').val('');
    $('#send-button').css('display', 'none');
    if (user_input) {
        appendMessage('You', user_input);
        sendChatRequest('/api/question', { 'question': user_input});
    }
});


$(document).on('click', '.profile-image', function () {
    $('.profile-image').removeClass('highlighted');
    $(this).addClass('highlighted');
    let firstName = $(this).find('img').attr('alt').split(' ')[0];
    let lastName = $(this).find('img').attr('alt').split(' ')[1];
    let profile = {
        first_name: firstName,
        last_name: lastName
    };
    sendChatRequest('/api/start_chat', { 'profile': profile });
});



$(document).on('click', '.plus-sign', function () {
    console.log('plus sign clicked');
    $(this).hide(); // Hide the plus sign as requested

    createNewProfileContainer();
});



$(document).on('click', '.document img', function () {
    showBigImage($(this).attr('src'));
});

$(document).on('click', '.delete-icon', function () {
    let documentName = $(this).siblings('p').text();
    sendChatRequest('/api/delete_profile', { 'document_name': documentName });
});
