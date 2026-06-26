// Demo data used as a fallback when the server has no records yet, so the
// prototype is explorable offline. Treat all of this as fictional.

export const STATUS = {
  missing: { bg: '#FDE7E7', fg: '#C2272D' },
  sighted: { bg: '#FBEEDA', fg: '#9A6400' },
  safe: { bg: '#E3F2E7', fg: '#1B7A45' },
  care: { bg: '#E4EEF6', fg: '#1F5E96' },
}

export const DEMO_PEOPLE = [
  { id: 'p1', disaster: 'd1', name: 'María Fernanda Rojas', gender: 'F', age: 7, status: 'missing',
    place: 'Las Tejerías, Aragua', date: '9 jun 2026, ~14:00',
    clothes: 'Vestido azul · zapatos rojos · cicatriz en la frente',
    desc: 'Cabello castaño hasta los hombros. Hablaba poco por el susto. Se separó de su familia durante la evacuación por las lluvias.',
    reportedBy: 'Su tía Carmen · Miami, EE. UU.',
    updates: [
      { t: 'Reporte creado por su tía', s: '9 jun · 14:20 · Miami', k: 'missing' },
      { t: 'Voluntario revisó la quebrada El Limón', s: '10 jun · 09:10', k: 'sighted' },
      { t: 'Posible avistamiento sin confirmar', s: '11 jun · Las Tejerías', k: 'sighted' },
    ] },
  { id: 'p2', disaster: 'd1', name: 'José Antonio Mendoza', gender: 'M', age: 64, status: 'safe',
    place: 'Refugio Cancha Cubierta, La Guaira', date: '10 jun 2026',
    clothes: 'Camisa gris · usa bastón',
    desc: 'Registrado a salvo por el personal del refugio. En buen estado de salud, busca a su hija Ana Lucía.',
    reportedBy: 'Refugio Cancha Cubierta',
    updates: [
      { t: 'Registrado a salvo en el refugio', s: '10 jun · 18:00', k: 'safe' },
      { t: 'Solicita contactar a su hija', s: '10 jun · 18:30', k: 'care' },
    ] },
  { id: 'p3', disaster: 'd1', name: 'Carlos Daniel Pérez', gender: 'M', age: 23, status: 'sighted',
    place: 'Cerca del Río Guaire, Caracas', date: '11 jun 2026',
    clothes: 'Chaqueta negra · gorra roja',
    desc: 'Visto por un voluntario ayudando a sacar agua de viviendas. No se ha podido confirmar su identidad.',
    reportedBy: 'Voluntario verificado',
    updates: [
      { t: 'Reporte creado por su hermano', s: '9 jun · 20:00 · Bogotá', k: 'missing' },
      { t: 'Avistamiento reportado por voluntario', s: '11 jun · 12:40', k: 'sighted' },
    ] },
  { id: 'p4', disaster: 'd1', name: 'Ana Lucía Gómez', gender: 'F', age: 34, status: 'missing',
    place: 'Sector La Guaira, vía principal', date: '9 jun 2026',
    clothes: 'Suéter beige · embarazada',
    desc: 'Salió a buscar a su padre José Antonio y no regresó. Su teléfono está apagado desde la noche del 9.',
    reportedBy: 'Su esposo · Valencia',
    updates: [
      { t: 'Reporte creado por su esposo', s: '9 jun · 22:10', k: 'missing' },
    ] },
  { id: 'p5', disaster: 'd1', name: 'Niño no identificado (~4 años)', gender: 'M', age: 4, status: 'care',
    place: 'Hospital Pérez de León II, Petare', date: '10 jun 2026',
    clothes: 'Pijama amarillo · sin documentos',
    desc: 'Menor no acompañado bajo cuidado médico. Estable. El hospital busca a sus familiares — si lo reconoces, abre una pista.',
    reportedBy: 'Hospital Pérez de León II',
    updates: [
      { t: 'Ingresado como menor no acompañado', s: '10 jun · 06:30', k: 'care' },
      { t: 'Ficha publicada para localizar familia', s: '10 jun · 11:00', k: 'care' },
    ] },
  { id: 'p6', disaster: 'd1', name: 'Familia Castillo (3 personas)', gender: 'M', age: 0, status: 'safe',
    place: 'Refugio Escuela Bolivariana, Maiquetía', date: '10 jun 2026',
    clothes: 'Madre y dos niños',
    desc: 'Familia completa registrada a salvo en el refugio. Buscan a un primo, Carlos Daniel.',
    reportedBy: 'Refugio Escuela Bolivariana',
    updates: [
      { t: 'Familia registrada a salvo', s: '10 jun · 16:00', k: 'safe' },
    ] },
  { id: 'p7', disaster: 'd2', name: 'Jean-Baptiste Pierre', gender: 'M', age: 29, status: 'missing',
    place: 'Carrefour, Puerto Príncipe', date: '2 jun 2026',
    clothes: 'Camiseta blanca · sandalias',
    desc: 'Se separó de su familia tras el sismo. Su madre lo busca desde Santo Domingo.',
    reportedBy: 'Su madre · Santo Domingo',
    updates: [
      { t: 'Reporte creado por su madre', s: '2 jun · 21:00 · Santo Domingo', k: 'missing' },
    ] },
  { id: 'p8', disaster: 'd2', name: 'Mirlande Joseph', gender: 'F', age: 8, status: 'care',
    place: 'Hôpital Général, Puerto Príncipe', date: '3 jun 2026',
    clothes: 'Vestido rosado · sin documentos',
    desc: 'Menor no acompañada bajo cuidado médico. Estable. El hospital busca a sus familiares.',
    reportedBy: 'Hôpital Général',
    updates: [
      { t: 'Ingresada como menor no acompañada', s: '3 jun · 08:00', k: 'care' },
      { t: 'Ficha publicada para localizar familia', s: '3 jun · 12:30', k: 'care' },
    ] },
  { id: 'p9', disaster: 'd3', name: 'Yorman Salcedo', gender: 'M', age: 41, status: 'sighted',
    place: 'El Limón, La Guaira', date: '12 jun 2026',
    clothes: 'Overol azul · botas de trabajo',
    desc: 'Visto ayudando en labores de rescate. Identidad sin confirmar.',
    reportedBy: 'Voluntario verificado',
    updates: [
      { t: 'Avistamiento reportado por voluntario', s: '12 jun · 15:00', k: 'sighted' },
    ] },
]

export const DEMO_INSTI = [
  { disaster: 'd1', name: 'Refugio Cancha Cubierta', loc: 'La Guaira', count: '128 personas', minors: '6 menores no acompañados', kind: 'refugio' },
  { disaster: 'd1', name: 'Hospital Pérez de León II', loc: 'Petare, Caracas', count: '43 pacientes', minors: '2 menores no acompañados', kind: 'hospital' },
  { disaster: 'd1', name: 'Refugio Escuela Bolivariana', loc: 'Maiquetía', count: '210 personas', minors: '', kind: 'refugio' },
  { disaster: 'd1', name: 'Hospital Vargas', loc: 'Caracas', count: '67 pacientes', minors: '1 menor no acompañado', kind: 'hospital' },
  { disaster: 'd2', name: 'Hôpital Général', loc: 'Puerto Príncipe', count: '305 pacientes', minors: '14 menores no acompañados', kind: 'hospital' },
  { disaster: 'd2', name: 'Refugio Croix-des-Bouquets', loc: 'Ouest, Haití', count: '480 personas', minors: '9 menores no acompañados', kind: 'refugio' },
  { disaster: 'd3', name: 'Refugio Maiquetía Norte', loc: 'La Guaira', count: '96 personas', minors: '', kind: 'refugio' },
]

export const DEMO_MINE = [
  { name: 'María Fernanda Rojas', sub: 'Esperando conexión · creado hace 6 min', state: 'queued' },
  { name: 'Actualización · Carlos D. Pérez', sub: 'Avistamiento añadido · 11 jun', state: 'sent' },
  { name: 'Ana Lucía Gómez', sub: 'Sincronizado · 10 jun', state: 'sent' },
]

export const DEMO_ACT = [
  { disaster: 'd1', t: 'José A. Mendoza marcado A SALVO', s: 'Refugio Cancha Cubierta · hace 12 min', k: 'safe' },
  { disaster: 'd1', t: 'Nuevo reporte: Ana Lucía Gómez', s: 'La Guaira · hace 25 min', k: 'missing' },
  { disaster: 'd1', t: 'Hospital Pérez de León publicó 5 personas', s: 'Petare · hace 1 h', k: 'care' },
  { disaster: 'd2', t: 'Mirlande Joseph bajo cuidado médico', s: 'Hôpital Général · hace 40 min', k: 'care' },
  { disaster: 'd2', t: 'Nuevo reporte: Jean-Baptiste Pierre', s: 'Carrefour · hace 2 h', k: 'missing' },
  { disaster: 'd3', t: 'Avistamiento: Yorman Salcedo', s: 'El Limón · hace 3 h', k: 'sighted' },
]

export const DEMO_DISASTERS = [
  { id: 'd1', name: 'Inundaciones Las Tejerías', region: 'Aragua · Venezuela', type: 'flood', tag: 'INUND', date: '9 jun 2026', affected: '1.284', shelters: 7, status: 'Activa' },
  { id: 'd2', name: 'Terremoto Puerto Príncipe', region: 'Ouest · Haití', type: 'quake', tag: 'SISMO', date: '2 jun 2026', affected: '3.940', shelters: 21, status: 'Activa' },
  { id: 'd3', name: 'Deslaves de El Limón', region: 'La Guaira · Venezuela', type: 'landslide', tag: 'DESLA', date: '12 jun 2026', affected: '612', shelters: 4, status: 'Activa' },
]
