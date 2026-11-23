const calendarEvents = document.getElementById('calendar-events');
const pastToggle = document.getElementById('show-past');
const events = Array.from(calendarEvents.children);

function peruDate() {
    const formatter = new Intl.DateTimeFormat('en', {
        timeZone: 'America/Lima',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
    });
    const parts = Object.fromEntries(formatter.formatToParts(new Date()).map(({ type, value }) => [type, value]));
    return [parts.year, parts.month, parts.day].join('-');
}

function updateCalendar() {
    const today = peruDate();

    for (const event of events) {
        const past = event.dataset.fecha < today;
        const sameDay = event.dataset.fecha === today;
        const state = event.querySelector('.event-state');
        state.textContent = past ? 'Fecha pasada' : 'Hoy';
        state.hidden = !(past || sameDay);
        state.classList.toggle('is-past', past);
        event.querySelector('.registration-state').hidden = !event.dataset.cierre || event.dataset.cierre >= today;
        event.hidden = past && !pastToggle.checked;
    }

    const empty = events.every(event => event.hidden);
    calendarEvents.hidden = empty;
    document.getElementById('calendar-empty').hidden = !empty;
}

pastToggle.addEventListener('change', updateCalendar);
document.getElementById('calendar-controls').hidden = false;
updateCalendar();

const search = document.getElementById('directory-search');
const directory = Array.from(document.getElementById('directory-list').children);
const noResults = document.getElementById('directory-empty');

function searchable(text) {
    return text.toLocaleLowerCase('es-PE').normalize('NFD').replace(/\p{M}/gu, '');
}

search.addEventListener('input', () => {
    const query = searchable(search.value.trim());
    for (const entry of directory) {
        entry.hidden = !searchable(entry.textContent).includes(query);
    }
    noResults.hidden = directory.some(entry => !entry.hidden);
});

document.getElementById('directory-filter').hidden = false;
