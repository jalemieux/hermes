// Update the fetch calls in your JavaScript to use the new flash message system

// For the generate summary button:
fetch('/generate-summary', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'
    }
})
.then(response => response.json())
.then(data => {
    if (data.status === 'success') {
        showFlashMessage(data.message, 'success');
    } else {
        showFlashMessage(data.message, 'error');
    }
})
.catch(error => {
    showFlashMessage('An error occurred. Please try again.', 'error');
});

// For the email forwarding toggle:
fetch('/api/email-forwarder', {
    method: method,
    headers: {
        'Content-Type': 'application/json'
    }
})
.then(response => response.json())
.then(data => {
    if (data.status === 'success') {
        showFlashMessage(data.message, 'success');
    } else {
        showFlashMessage(data.message, 'error');
    }
})
.catch(error => {
    showFlashMessage('An error occurred. Please try again.', 'error');
}); 