import { getCookie } from '../utils/cookies.js';

function initializeProfileEvents() {
    document.getElementById('plus-sign').addEventListener('click', function () {
        console.log('clicked');
        getProfileCreationForm();
    });

    let profileIcons = document.getElementsByClassName('profile-img');
    for (let i = 0; i < profileIcons.length; i++) {
        profileIcons[i].addEventListener('click', function () {
            const first_name = this.getAttribute('first_name');
            const last_name = this.getAttribute('last_name');
            let profile = {
                first_name: first_name,
                last_name: last_name
            };
            startChat(profile);

            this.classList.add('highlighted');

            for (let j = 0; j < profileIcons.length; j++) {
                if (j !== i) {
                    profileIcons[j].classList.remove('highlighted');
                }
            }
        });
    }
};
function handleFileInputChange(event) {
    const fileInput = event.target;
    const file = fileInput.files[0];
    const imagePreview = document.getElementById('image-preview');
    const imageInstructions = document.getElementById('image-instructions');

    if (file && file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = function (e) {
            const image = document.createElement('img');
            image.src = e.target.result;
            image.classList.add('max-w-full', 'h-auto');
            imagePreview.innerHTML = '';
            imagePreview.appendChild(image);
            imagePreview.classList.remove('hidden');
            imageInstructions.classList.add('hidden');
        };
        reader.readAsDataURL(file);
    } else {
        imagePreview.innerHTML = 'Invalid file format';
        imagePreview.classList.remove('hidden');
        imageInstructions.classList.add('hidden');
    }
}

function initializeProfileCreationEvents() {
    document.getElementById('file-input').addEventListener('change', handleFileInputChange);
    document.getElementById('create-profile').addEventListener('click', function (event) {
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
        event.target.classList.add('hidden');
        document.getElementById('loading-animation').classList.remove('hidden');
        createProfile(formData);
    });
}

function initializeDocumentEvents() {
    let documentImages = document.getElementsByClassName('document-img');
    for (let i = 0; i < documentImages.length; i++) {
        documentImages[i].addEventListener('click', function () {
            let img = documentImages[i].querySelector('img');
            let src = img.getAttribute('src');

            let bigImage = document.createElement('img');
            bigImage.setAttribute('src', src);

            let bigImageContainer = document.createElement('div');
            bigImageContainer.classList.add('big-image-container');
            bigImageContainer.appendChild(bigImage);

            let closeButton = document.createElement('button');
            closeButton.textContent = 'Close';
            closeButton.classList.add('close-button');
            bigImageContainer.appendChild(closeButton);

            document.body.appendChild(bigImageContainer);

            closeButton.addEventListener('click', function () {
                bigImageContainer.remove();
            });
        });
    }
}

async function loadNextPage(gridContainer, nextIndex) {
    hideChatForm();
    const fetchOptions = {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(
            {
                'container_id': gridContainer.getAttribute('id'),
                'page': nextIndex
            }
        ),
    };
    const response = await fetch('api/load_next_page', fetchOptions);
    const reader = response.body.getReader();
    let done = false;
    while (!done) {
        const { value, done: resultDone } = await reader.read();
        done = resultDone;
        if (value) {
            const json = JSON.parse(new TextDecoder('utf-8').decode(value));
            document.getElementById(json.container_id).innerHTML += json.content;
        }
    }
    await initializeMessageEvents();
    showChatForm();
}

async function getNextPage(containerId) {
    let gridContainer = document.getElementById(containerId);
    let messageContainer = gridContainer.closest('.job-offers-message-container')
    let grids = gridContainer.getElementsByClassName('job-offer-grid');
    let displayedGrid = Array.from(grids).find(grid => !grid.classList.contains('hidden'));
    if (!displayedGrid) {
        return;
    }
    let currentIndex = parseInt(displayedGrid.getAttribute('page'));
    let loadedPages = parseInt(messageContainer.getElementsByClassName('total-pages')[0].textContent);
    let nextIndex = currentIndex + 1;
    messageContainer.getElementsByClassName('page-number')[0].textContent = nextIndex;
    if (currentIndex < loadedPages) {
        let nextGrid = Array.from(grids).find(grid => grid.getAttribute('page') === nextIndex.toString());
        if (nextGrid) {
            displayedGrid.classList.add('hidden');
            nextGrid.classList.remove('hidden');
        }
    } else {
        messageContainer.getElementsByClassName('total-pages')[0].textContent = loadedPages + 1;
        displayedGrid.classList.add('hidden');
        await loadNextPage(gridContainer, nextIndex);
    }
}


function getPreviousPage(containerId) {
    let gridContainer = document.getElementById(containerId);
    let messageContainer = gridContainer.closest('.job-offers-message-container')
    let grids = gridContainer.getElementsByClassName('job-offer-grid');
    let displayedGrid = Array.from(grids).find(grid => !grid.classList.contains('hidden'));
    if (!displayedGrid) {
        return;
    }
    let currentIndex = displayedGrid.getAttribute('page');
    if (currentIndex > 1) {
        let previousIndex = parseInt(currentIndex) - 1;
        messageContainer.getElementsByClassName('page-number')[0].textContent = previousIndex;
        let previousGrid = Array.from(grids).find(grid => grid.getAttribute('page') === previousIndex.toString());
        if (previousGrid) {
            displayedGrid.classList.add('hidden');
            previousGrid.classList.remove('hidden');
        }
    }
}


async function initializeMessageEvents() {
    function addEventListenerOnce(element, eventType, handler) {
        if (!element.hasAttribute('listener-added')) {
            element.addEventListener(eventType, handler);
            element.setAttribute('listener-added', 'true');
        }
    }

    let jobOffers = document.getElementsByClassName('job-offer');
    for (let i = 0; i < jobOffers.length; i++) {
        jobOffers[i].addEventListener('click', function () {
            let detailedView = jobOffers[i].querySelector('.detailed-view');
            toggleJobOffersInGrid(jobOffers[i]);
            detailedView.classList.toggle('hidden');
        });
    }

    let applyButtons = document.getElementsByClassName('offer-focus');
    for (let i = 0; i < applyButtons.length; i++) {
        applyButtons[i].addEventListener('click', function () {
            let reference = applyButtons[i].getAttribute('reference');
             getOfferFocus(reference);
        });
    }

    let nextPageButtons = document.getElementsByClassName('next-page');
    for (let i = 0; i < nextPageButtons.length; i++) {
        addEventListenerOnce(nextPageButtons[i], 'click', async function () {
            let containerId = nextPageButtons[i].closest('.job-offers-message-container').getAttribute('container_id');
            await getNextPage(containerId);
        });
    }

    let previousPageButtons = document.getElementsByClassName('previous-page');
    for (let i = 0; i < previousPageButtons.length; i++) {
        addEventListenerOnce(previousPageButtons[i], 'click', function () {
            let containerId = previousPageButtons[i].closest('.job-offers-message-container').getAttribute('container_id');
            getPreviousPage(containerId);
        });
    }
}

function toggleJobOffersInGrid(currentOffer) {
    let grid = currentOffer.closest('.job-offer-grid');
    let jobOffersInGrid = grid.getElementsByClassName('job-offer');
    for (let i = 0; i < jobOffersInGrid.length; i++) {
        if (jobOffersInGrid[i] !== currentOffer) {
            jobOffersInGrid[i].classList.toggle('hidden');
        }
    }
}

function initializeOfferFocusEvents() {
    initializeDocumentEvents();
}

async function getOfferFocus(reference) {
    hideChatForm();
    emptyMessageContainer();
    const fetchOptions = {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 'offer_id': reference }),
    };
    const response = await fetch('/api/get_offer_focus', fetchOptions);
    const reader = response.body.getReader();
    let done = false;
    while (!done) {
        const { value, done: resultDone } = await reader.read();
        done = resultDone;
        if (value) {
            const text = new TextDecoder('utf-8').decode(value);
            document.getElementById('message-container').innerHTML += text;
            initializeMessageEvents();
            initializeOfferFocusEvents();
        }
    }
    showChatForm();
}

export function getProfiles() {
    const fetchOptions = {
        method: 'GET',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
        },
    };
    fetch('/api/get_profiles', fetchOptions)
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
            emptyMessageContainer();
            document.getElementById('message-container').innerHTML += data;
            getDocuments(profile);
            showChatForm();
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
            initializeDocumentEvents();
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

function showChatForm() {
    document.getElementById('chat-form').classList.remove('hidden');
}

function hideChatForm() {
    document.getElementById('chat-form').classList.add('hidden');
}

function emptyMessageContainer() {
    document.getElementById('message-container').innerHTML = '';
}

export async function sendQuestion(question) {
    hideChatForm();
    const fetchOptions = {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question: question }),
    };
    const response = await fetch('/api/question', fetchOptions);
    const reader = response.body.getReader();
    let done = false;
    while (!done) {
        const { value, done: resultDone } = await reader.read();
        done = resultDone;
        if (value) {
            const json = JSON.parse(new TextDecoder('utf-8').decode(value));
            if (json.container_id) {
                document.getElementById(json.container_id).innerHTML += json.content;
            } else {
                document.getElementById('message-container').innerHTML += json.content;
            }
            await initializeMessageEvents();
        }
    }
    showChatForm();
}
