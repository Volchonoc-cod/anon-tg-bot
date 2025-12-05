/**
 * Основные JavaScript функции для ShadowTalk
 */

// Обновление времени
function updateCurrentTime() {
    const now = new Date();
    const timeElement = document.getElementById('current-time');
    if (timeElement) {
        timeElement.textContent = now.toLocaleTimeString('ru-RU');
    }
}

// Авто-обновление статистики
function refreshStats() {
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            // Обновляем все элементы с классами stat-value
            document.querySelectorAll('.stat-value[data-stat]').forEach(element => {
                const stat = element.getAttribute('data-stat');
                if (data[stat] !== undefined) {
                    element.textContent = data[stat];
                }
            });
        })
        .catch(error => console.error('Ошибка обновления статистики:', error));
}

// Модальное окно
function showModal(title, content) {
    const modal = document.createElement('div');
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
    `;
    
    modal.innerHTML = `
        <div style="
            background: white;
            padding: 30px;
            border-radius: 20px;
            max-width: 500px;
            width: 90%;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        ">
            <h2 style="margin-bottom: 20px;">${title}</h2>
            <div style="margin-bottom: 30px;">${content}</div>
            <div style="display: flex; justify-content: flex-end; gap: 10px;">
                <button onclick="this.closest('.modal').remove()" class="btn">
                    Закрыть
                </button>
            </div>
        </div>
    `;
    
    modal.classList.add('modal');
    document.body.appendChild(modal);
    
    // Закрытие по клику на фон
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });
}

// Уведомление
function showNotification(message, type = 'info') {
    const colors = {
        info: '#6366f1',
        success: '#10b981',
        warning: '#f59e0b',
        error: '#ef4444'
    };
    
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${colors[type] || colors.info};
        color: white;
        padding: 15px 25px;
        border-radius: 10px;
        box-shadow: 0 5px 20px rgba(0, 0, 0, 0.2);
        z-index: 1000;
        animation: slideIn 0.3s ease;
        max-width: 400px;
    `;
    
    notification.textContent = message;
    document.body.appendChild(notification);
    
    // Авто-удаление через 5 секунд
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

// Анимации
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(-10px); }
        to { opacity: 1; transform: translateY(0); }
    }
`;
document.head.appendChild(style);

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    updateCurrentTime();
    setInterval(updateCurrentTime, 1000);
    
    // Обновляем статистику каждые 30 секунд
    setInterval(refreshStats, 30000);
    
    // Плавная анимация загрузки
    document.body.style.animation = 'fadeIn 0.5s ease';
    
    // Подсветка активной страницы в навигации
    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-tab').forEach(tab => {
        const href = tab.getAttribute('href');
        if (href === currentPath || (href === '/' && currentPath === '')) {
            tab.classList.add('active');
        }
    });
});

// Экспорт функций в глобальную область видимости
window.updateCurrentTime = updateCurrentTime;
window.refreshStats = refreshStats;
window.showModal = showModal;
window.showNotification = showNotification;
