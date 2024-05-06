let totalTokensUsed = 0;
let totalPricePaid = 0;
let isSendButtonDisabled = false;

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        let cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            let cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
function formatJson(obj, level = 0) {
    let indent = '  '.repeat(level);
    let formattedString = '';

    function wrapWithClass(value, cssClass) {
        return `<span class="${cssClass}">${value}</span>`;
    }

    if (Array.isArray(obj)) {
        formattedString += wrapWithClass('[', 'array');
        for (let i = 0; i < obj.length; i++) {
            formattedString += '\n' + indent + '  ' + formatJson(obj[i], level + 1);
            if (i < obj.length - 1) {
                formattedString += ',' + '\n' + indent + '  ';
            }
        }
        formattedString += wrapWithClass('\n' + indent + ']', 'array');
    } else if (typeof obj === 'object' && obj !== null) {
        formattedString += wrapWithClass('{', 'object');
        for (let key in obj) {
            formattedString += '\n' + indent + '  ' + wrapWithClass(`"${key}": `, 'key');
            formattedString += formatJson(obj[key], level + 1);
            if (Object.keys(obj).indexOf(key) < Object.keys(obj).length - 1) {
                formattedString += ',' + '\n' + indent + '  ';
            }
        }
        formattedString += wrapWithClass('\n' + indent + '}', 'object');
    } else if (typeof obj === 'string') {
        formattedString += wrapWithClass(`"${obj}"`, 'string');
    } else if (typeof obj === 'number') {
        formattedString += wrapWithClass(obj.toString(), 'number');
    } else if (typeof obj === 'boolean') {
        formattedString += wrapWithClass(obj.toString(), 'boolean');
    } else if (obj === null) {
        formattedString += wrapWithClass('null', 'null');
    }

    return formattedString;
}



function appendMessage(role, message, isMarkdown = false) {
    let chatMessage;
    if (role == 'tool') {
        message = JSON.parse(message);
        let name = message.name;
        let arguments = message.arguments;
        let formattedJson = formatJson(message.result);
        chatMessage = $('<div>').addClass('message-container').addClass('json-message').html(`<p>${name} ${arguments}</p>${formattedJson}`);
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



function updateTokenCounter(tokensUsed) {
    totalTokensUsed = tokensUsed;
    $('#token-counter').text('MistralAI Total Tokens Used: ' + totalTokensUsed);
}

function updateTotalPriceCounter(tokensUsed) {
    let pricePaid = (tokensUsed / 1000) * 0.01;
    totalPricePaid += pricePaid;
    $('#total-price-counter').text('Total Price Paid: $' + totalPricePaid.toFixed(2));
}

function updateCounters(tokensUsed) {
    updateTokenCounter(tokensUsed);
    updateTotalPriceCounter(tokensUsed);
}

function updateProfiles(profiles) {
    let profileImagesDiv = $('.profile-images');
    profileImagesDiv.empty();

    profiles.forEach(profile => {
        let profileImageDiv = $('<div>').addClass('profile-image');
        let profileImage = $('<img>').attr('src', 'static/images/user_images/profile/' + profile.photo_url).attr('alt', profile.first_name + ' ' + profile.last_name);

        profileImageDiv.append(profileImage);
        profileImagesDiv.append(profileImageDiv);
    });
}

function updateUserDocuments(documents) {
    let profileDisplayDiv = $('#profile-display');
    profileDisplayDiv.empty();
    documents.forEach(document => {
        let documentDiv = $('<div>').addClass('document');
        let documentName = $('<p>').text(document.name);
        let documentThumbnail = $('<img>').attr('src', document.path).attr('alt', document.name);

        documentDiv.append(documentName);

        if (document.name !== 'default_profile.json') {
            let deleteIcon = $('<img>').attr('src', 'static/images/trash.png').addClass('delete-icon');
            documentDiv.append(deleteIcon);
        }

        documentDiv.append(documentThumbnail);
        profileDisplayDiv.append(documentDiv);
    });
}

function handleResponse(data) {
    let message_role = data.role;
    let message_content = data.content;
    if (data.is_last) {
        isSendButtonDisabled = false;
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
        if (message_content.name == 'talk') {
            apppendMessage('assistant', message_content.result, false);
        } else {
            appendMessage(message_role, message_content, false);
        }
    } else if (message_role == 'get_profiles') {
        updateProfiles(message_content);
    }
}

async function sendChatRequest(url, data) {
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
        },
        body: JSON.stringify(data),
    });

    if (response.ok) {
        if (data.input_type === 'start_chat') {
            const jsonResponse = await response.json();
            handleResponse(jsonResponse);
        } else {
            const reader = response.body.getReader();
            let done = false;

            while (!done) {
                const { value, done: resultDone } = await reader.read();
                done = resultDone;

                if (value) {
                    const text = new TextDecoder('utf-8').decode(value);
                    const jsonResponse = JSON.parse(text);
                    handleResponse(jsonResponse);
                }
            }
        }
    } else {
        console.error('Error:', response.status, response.statusText);
    }
}

function showBigImage(src) {
    let bigImage = $('<img>').attr('src', src);
    let bigImageContainer = $('<div>').addClass('big-image-container').append(bigImage);
    let closeButton = $('<button>').text('Close').addClass('close-button');
    bigImageContainer.append(closeButton);
    $('body').append(bigImageContainer);
    closeButton.on('click', function () {
        bigImageContainer.remove();
    });
}


$(document).ready(function () {
    sendChatRequest('', { 'user_input': '', 'input_type': 'get_profiles' });
});

$('#chat-form').on('submit', function (e) {
    e.preventDefault();
    let user_input = $('#user_input').val();
    $('#user_input').val('');
    isSendButtonDisabled = true;
    $('#send-button').css('display', 'none');
    if (user_input) {
        appendMessage('You', user_input);
        sendChatRequest('', { 'user_input': user_input, 'input_type': 'question' });
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
    sendChatRequest('', { 'user_input': profile, 'input_type': 'start_chat' });
});


$(document).on('click', '.plus-sign', function () {
    let component = $('<div>').addClass('new-profile-container');
    let firstNameInput = $('<input>').attr('type', 'text').attr('placeholder', 'First Name');
    let lastNameInput = $('<input>').attr('type', 'text').attr('placeholder', 'Last Name');
    let profileInfoInput = $('<textarea>').attr('placeholder', 'Profile Information');
    let sendButton = $('<button>').text('Send').addClass('send-button');
    component.append(firstNameInput, lastNameInput, profileInfoInput, sendButton);
    $('#chat_window').append(component);

    sendButton.on('click', function () {
        let firstName = firstNameInput.val();
        let lastName = lastNameInput.val();
        let profileInfo = profileInfoInput.val();
        let profile = {
            first_name: firstName,
            last_name: lastName,
            profile_info: profileInfo
        };
        sendChatRequest('', { 'user_input': profile, 'input_type': 'create_profile' });
    });
});


$(document).on('click', '.document img', function () {
    showBigImage($(this).attr('src'));
});

$(document).on('click', '.delete-icon', function () {
    let documentName = $(this).siblings('p').text();
    sendChatRequest('', { 'user_input': { 'name': documentName }, 'input_type': 'delete_profile' });
});
