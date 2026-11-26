import { getStore } from '@netlify/blobs';

const formatoDia = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Lima', year: 'numeric', month: '2-digit', day: '2-digit'
});
const PUNTOS_POR_VISITA = 124;
const headers = { 'Cache-Control': 'no-store' };

async function registrarVisita(almacen, dia) {
    for (let intento = 0; intento < 10; intento += 1) {
        const registro = await almacen.getWithMetadata(dia, { type: 'json' });
        const puntos = (registro?.data ?? 0) + PUNTOS_POR_VISITA;
        const condicion = registro ? { onlyIfMatch: registro.etag } : { onlyIfNew: true };
        const { modified } = await almacen.setJSON(dia, puntos, condicion);
        if (modified) return puntos;
        await new Promise((resolve) => setTimeout(resolve, 25 + Math.random() * 50));
    }
    return null;
}

export default async function visitas(request) {
    if (request.method !== 'GET' && request.method !== 'POST') {
        return new Response(null, { status: 405, headers: { ...headers, Allow: 'GET, POST' } });
    }
    if (request.method === 'POST' && request.headers.get('Sec-Fetch-Site') === 'cross-site') {
        return new Response(null, { status: 403, headers });
    }
    const dia = formatoDia.format(new Date());
    try {
        const almacen = getStore({ name: 'actividad-portada', consistency: 'strong' });
        const puntos = request.method === 'GET'
            ? (await almacen.get(dia, { type: 'json' })) ?? 0
            : await registrarVisita(almacen, dia);
        if (puntos !== null) return Response.json({ dia, puntos }, { headers });
    } catch (error) {
        console.error('Error al consultar o guardar la actividad de portada', error);
    }
    return new Response(null, { status: 503, headers });
}
