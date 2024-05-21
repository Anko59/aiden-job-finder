import { getCookie } from '../utils/cookies.js';

function initializeProfileEvents() {
    document.getElementById('plus-sign').addEventListener('click', function() {
        console.log('clicked');
        getProfileCreationForm();
    });

    let profileIcons = document.getElementsByClassName('profile-img');
    for(let i = 0; i < profileIcons.length; i++) {
        profileIcons[i].addEventListener('click', function() {
            const first_name = this.getAttribute('first_name');
            const last_name = this.getAttribute('last_name');
            let profile = {
                first_name: first_name,
                last_name: last_name
            };
            startChat(profile);
        });
    }
};

function initializeProfileCreationEvents() {
    document.getElementById('create-profile').addEventListener('click', function(event) {
        event.preventDefault();
        let firstName = document.getElementById('first_name').value;
        let lastName = document.getElementById('last_name').value;
        let profileInfo = document.getElementById('prompt-input').value;
        let photoFile = document.getElementById('file-input').files[0];
        let formData = new FormData();
        formData.append('first_name', firstName);
        formData.append('last_name', lastName);
        formData.append('profile_info', profileInfo);
        formData.append('photo', photoFile);
        createProfile(formData);
    });
};

export function getProfiles() {
    const fetchOptions = {
        method: 'GET',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
        },
    };
    fetch('api/get_profiles', fetchOptions)
        .then(response => response.text())
        .then(data => {
            document.getElementById('profile-container').innerHTML = data;
            initializeProfileEvents();
        })
        .catch(error => {
            console.error('Error:', error);
        });
};

export function getProfileCreationForm() {
    const fetchOptions = {
        method: 'GET',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
        },
    };
    fetch('/api/get_profile_creation_form', fetchOptions)
        .then(response => response.text())
        .then(result => {
            document.getElementById('message-container').innerHTML += result;
            initializeProfileCreationEvents();
        })
        .catch(error => {
            console.error('Error:', error);
        });
};

export function startChat(profile) {
    const fetchOptions = {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(profile),
    };
    fetch('/api/start_chat', fetchOptions)
        .then(response => response.text())
        .then(data => {
            document.getElementById('message-container').innerHTML += data;
            getDocuments(profile);
        })
        .catch(error => {
            console.error('Error:', error);
        });
};

export function getDocuments(profile) {
    const fetchOptions = {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(profile),
    };
    fetch('/api/get_documents', fetchOptions)
        .then(response => response.text())
        .then(data => {
            document.getElementById('documents-display').innerHTML = data;
        })
        .catch(error => {
            console.error('Error:', error);
        });
}


export function createProfile(formData) {
    const fetchOptions = {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: formData,
    };
    fetch('/api/create_profile', fetchOptions)
        .then(response => response.text())
        .then(data => {
            getProfiles();
            let nameDict = {};
            for (let pair of formData.entries()) {
                if (pair[0] === 'first_name' || pair[0] === 'last_name') {
                    nameDict[pair[0]] = pair[1];
                }
            }

            startChat(nameDict);
        })
        .catch(error => {
            console.error('Error:', error);
        });
};

export async function sendQuestion(question) {
    const fetchOptions = {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question: question }),
    };
    const response = await fetch('api/question', fetchOptions);
    const reader = response.body.getReader();
    let done = false;
    while (!done) {
        const { value, done: resultDone } = await reader.read();
        done = resultDone;
        if (value) {
            const text = new TextDecoder('utf-8').decode(value);
            document.getElementById('message-container').innerHTML += text;
        }
    }
}
