const calendarEvents = document.getElementById('calendar-events');
const controls = document.getElementById('calendar-controls');
const pastToggle = document.getElementById('show-past');
const publicToggle = document.getElementById('public-only');
const openToggle = document.getElementById('open-only');
const dateOrder = document.getElementById('date-order');
const events = Array.from(calendarEvents.children);

function orderCalendar() {
    const direction = dateOrder.value === 'desc' ? -1 : 1;
    const ordered = [...events].sort((a, b) => direction * a.dataset.fecha.localeCompare(b.dataset.fecha));
    calendarEvents.append(...ordered);
}

function peruDateTime() {
    const formatter = new Intl.DateTimeFormat('en', {
        timeZone: 'America/Lima',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hourCycle: 'h23'
    });
    const parts = Object.fromEntries(formatter.formatToParts(new Date()).map(({ type, value }) => [type, value]));
    return { date: [parts.year, parts.month, parts.day].join('-'), time: `${parts.hour}:${parts.minute}` };
}

function updateCalendar() {
    const { date: today, time: now } = peruDateTime();

    for (const event of events) {
        const past = event.dataset.fecha < today;
        const sameDay = event.dataset.fecha === today;
        const state = event.querySelector('.event-state');
        state.textContent = past ? 'Fecha pasada' : 'Hoy';
        state.hidden = !(past || sameDay);
        state.classList.toggle('is-past', past);
        const { apertura, cierre, horaCierre, tipo } = event.dataset;
        const expired = cierre && (cierre < today || (cierre === today && horaCierre && horaCierre <= now));
        const open = Boolean(apertura && cierre && apertura <= today && !expired && !past);
        const registration = event.querySelector('.registration-state');
        registration.textContent = open ? 'Inscripciones abiertas' :
            expired ? 'Plazo vencido' :
            apertura && apertura > today ? 'Inscripción próxima' : '';
        registration.hidden = !registration.textContent;
        registration.classList.toggle('is-open', open);
        event.hidden = (past && !pastToggle.checked) ||
            (publicToggle.checked && tipo !== 'publica') ||
            (openToggle.checked && !open);
    }

    const empty = events.every(event => event.hidden);
    calendarEvents.hidden = empty;
    document.getElementById('calendar-empty').hidden = !empty;
}

controls.addEventListener('change', updateCalendar);
dateOrder.addEventListener('change', orderCalendar);
controls.hidden = false;
orderCalendar();
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
