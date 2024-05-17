import { getCookie } from '../utils/cookies.js';
import { handleResponse } from './messageHandler.js';

export async function sendChatRequest(url, data, hasFile = false) {
    const fetchOptions = {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
        },
    };

    if (hasFile) {
        fetchOptions.body = data;
    } else {
        fetchOptions.headers['Content-Type'] = 'application/json';
        fetchOptions.body = JSON.stringify(data);
    }

    const response = await fetch(url, fetchOptions);
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
                    console.log(text);
                    const jsonResponse = JSON.parse(text);
                    handleResponse(jsonResponse);
                }
            }
        }
    } else {
        console.error('Error:', response.status, response.statusText);
    }
}
