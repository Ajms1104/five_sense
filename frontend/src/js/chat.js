// Rasa 챗봇 통신을 위한 함수 추가
async function sendMessageToRast(message) {
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: message })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.response || '서버 응답 오류');
        }
        
        const data = await response.json();
        return data.response;
    } catch (error) {
        console.error('챗봇 통신 오류:', error);
        return '죄송합니다. 현재 서버와 통신이 원활하지 않습니다.';
    }
}

// 입력칸 이벤트 리스너 설정
document.addEventListener('DOMContentLoaded', () => {
    const inputField = document.querySelector('.input-container input');
    const submitButton = document.querySelector('#submit');
    const chatHistory = document.querySelector('.chat-history');
    
    // 채팅 메시지 표시 함수
    function displayMessage(message, isUser = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${isUser ? 'user-message' : 'bot-message'}`;
        messageDiv.textContent = message;
        chatHistory.appendChild(messageDiv);
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }
    
    // 엔터키로 전송
    inputField.addEventListener('keypress', async (e) => {
        if (e.key === 'Enter') {
            const message = inputField.value.trim();
            if (message) {
                displayMessage(message, true);
                inputField.value = '';
                const response = await sendMessageToRast(message);
                displayMessage(response);
            }
        }
    });
    
    // 버튼 클릭으로 전송
    submitButton.addEventListener('click', async () => {
        const message = inputField.value.trim();
        if (message) {
            displayMessage(message, true);
            inputField.value = '';
            const response = await sendMessageToRast(message);
            displayMessage(response);
        }
    });
});