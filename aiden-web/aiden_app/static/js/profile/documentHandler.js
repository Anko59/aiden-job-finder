export function updateUserDocuments(documents) {
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


export function showBigImage(src) {
    let bigImage = $('<img>').attr('src', src);
    let bigImageContainer = $('<div>').addClass('big-image-container').append(bigImage);
    let closeButton = $('<button>').text('Close').addClass('close-button');
    bigImageContainer.append(closeButton);
    $('body').append(bigImageContainer);
    closeButton.on('click', function () {
        bigImageContainer.remove();
    });
}
