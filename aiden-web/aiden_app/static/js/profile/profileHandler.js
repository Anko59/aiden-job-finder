import { sendChatRequest } from '../chat/chatHandler.js';


export function updateProfiles(profiles) {
    let profileImagesDiv = $('.profile-images');
    profileImagesDiv.empty();

    profiles.forEach(profile => {
        let profileImageDiv = $('<div>').addClass('profile-image');
        let profileImage = $('<img>').attr('src', profile.photo_url).attr('alt', profile.first_name + ' ' + profile.last_name);

        profileImageDiv.append(profileImage);
        profileImagesDiv.append(profileImageDiv);
    });
    let plusSignDiv = $('<div>').addClass('plus-sign');
    let plusSign = $('<img>').attr('src', 'static/images/plus-sign.png');
    plusSignDiv.append(plusSign);
    profileImagesDiv.append(plusSignDiv);
}

export function createNewProfileContainer() {
    let component = $('<div>').addClass('new-profile-container');
    let firstNameInput = createInput('text', 'First Name', true, 'first-name-input');
    let lastNameInput = createInput('text', 'Last Name', true, 'last-name-input');
    let fileUploadLabel = createFileUploadLabel();
    let profileInfoHeader = $('<h5>').text('Paste all the information needed for the generation of your CVs in raw format:');
    let profileInfoInput = createInput('textarea', 'Profile Information', true, 'profile-info-input');
    let sendButton = createSendButton();

    component.append(firstNameInput, lastNameInput, fileUploadLabel, profileInfoHeader, profileInfoInput, sendButton);
    $('#chat-window').append(component);
}

function createInput(type, placeholder, required, id) {
    return $('<input>').attr('type', type).attr('placeholder', placeholder).attr('id', id).prop('required', required);
}

function createFileUploadLabel() {
    let fileUploadLabel = $('<label>').attr('for', 'file-upload').addClass('custom-file-upload');
    let fileUploadIcon = $('<i>').addClass('fa fa-cloud-upload');
    let photoInput = createInput('file', '', true, 'file-upload').attr('accept', 'image/*');
    let imgPreview = $('<img>').attr('id', 'img-preview').css({width: '100px', height: '100px', display: 'none'});

    fileUploadLabel.append(fileUploadIcon, "Profile photo", photoInput, imgPreview);

    photoInput.change(function() {
        if (this.files && this.files[0]) {
            var reader = new FileReader();

            reader.onload = function (e) {
                $('#img-preview').attr('src', e.target.result).css('display', 'block');
            }

            reader.readAsDataURL(this.files[0]);
        }
    });

    return fileUploadLabel;
}

function createSendButton() {
    let sendButton = $('<button>').text('Send').addClass('send-button');

    sendButton.on('click', function () {
        if (validateInputs()) {
            let firstName = $('#first-name-input').val();
            let lastName = $('#last-name-input').val();
            let profileInfo = $('#profile-info-input').val();
            let photoFile = $('#file-upload')[0].files[0];

            let formData = new FormData();
            formData.append('first_name', firstName);
            formData.append('last_name', lastName);
            formData.append('profile_info', profileInfo);
            formData.append('photo', photoFile);

            console.log(formData);
            sendChatRequest('/api/create_profile', formData, true);

            $('.plus-sign').show();
        } else {
            alert('Please fill all the fields.');
        }
    });

    return sendButton;
}

function validateInputs() {
    let inputs = $('#chat-window').find('input, textarea');
    for (let i = 0; i < inputs.length; i++) {
        if (!inputs[i].checkValidity()) {
            return false;
        }
    }
    return true;
}
