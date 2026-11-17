// Clinic content for the study prototype. Everything here is FICTIONAL:
// the clinic, the doctors and the task-card details are made up.

export const YEAR = 2026;
export const MONTH = 11; // 0-based: 11 = December

export const SPECIALTIES = [
  { id: 'general', icon: 'GP', en: 'General Medicine', ar: 'الطب العام', en_desc: 'Check-ups and common illness', ar_desc: 'فحوصات عامة وأمراض شائعة' },
  { id: 'paeds', icon: 'Ch', en: 'Paediatrics', ar: 'طب الأطفال', en_desc: 'Health care for children', ar_desc: 'رعاية صحة الأطفال' },
  { id: 'derm', icon: 'Sk', en: 'Dermatology', ar: 'الأمراض الجلدية', en_desc: 'Skin, hair and nails', ar_desc: 'الجلد والشعر والأظافر' },
  { id: 'eye', icon: 'Ey', en: 'Eye Care', ar: 'طب العيون', en_desc: 'Eye tests and eye problems', ar_desc: 'فحص النظر ومشاكل العين' },
  { id: 'dental', icon: 'Dn', en: 'Dentistry', ar: 'طب الأسنان', en_desc: 'Teeth and gums', ar_desc: 'الأسنان واللثة' },
  { id: 'heart', icon: 'Hr', en: 'Cardiology', ar: 'أمراض القلب', en_desc: 'Heart and blood pressure', ar_desc: 'القلب وضغط الدم' },
];

export const DOCTORS = [
  { id: 'rami', spec: 'general', en: 'Dr. Rami Saleh', ar: 'د. رامي صالح', years: 12 },
  { id: 'huda', spec: 'general', en: 'Dr. Huda Mansour', ar: 'د. هدى منصور', years: 9 },
  { id: 'lina', spec: 'paeds', en: 'Dr. Lina Haddad', ar: 'د. لينا حداد', years: 15 },
  { id: 'khaled', spec: 'paeds', en: 'Dr. Khaled Nasser', ar: 'د. خالد ناصر', years: 8 },
  { id: 'maha', spec: 'derm', en: 'Dr. Maha Qasem', ar: 'د. مها قاسم', years: 11 },
  { id: 'yousef', spec: 'eye', en: 'Dr. Yousef Barakat', ar: 'د. يوسف بركات', years: 14 },
  { id: 'nour', spec: 'dental', en: 'Dr. Nour Awad', ar: 'د. نور عوض', years: 7 },
  { id: 'samer', spec: 'heart', en: 'Dr. Samer Odeh', ar: 'د. سامر عودة', years: 18 },
];

// 16 slots, 9:00 to 16:30 every 30 minutes (minutes after midnight).
export const SLOTS = Array.from({ length: 16 }, (_, i) => 9 * 60 + i * 30);

// Two task cards of equal difficulty: each is the 2nd doctor of a 2-doctor
// specialty, a weekday in the middle of the month, and a slot in the middle
// of the slot grid. Name/phone/reason are fake values for the participant to type.
export const TASKS = {
  A: {
    spec: 'paeds', doctor: 'khaled', day: 15, slot: 10 * 60 + 30,
    name: { en: 'Sara Ahmad', ar: 'سارة أحمد' },
    phone: '0790000111',
    reason: { en: 'Fever and cough', ar: 'حرارة وسعال' },
  },
  B: {
    spec: 'general', doctor: 'huda', day: 23, slot: 13 * 60 + 30,
    name: { en: 'Omar Ali', ar: 'عمر علي' },
    phone: '0790000222',
    reason: { en: 'Back pain', ar: 'ألم في الظهر' },
  },
};

// Simple deterministic hash so availability is the same every time.
function hash(a, b) {
  let h = (a * 374761393 + b * 668265263) >>> 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177) >>> 0;
  return (h ^ (h >>> 16)) >>> 0;
}

function isTaskBooking(doctorId, day, slot) {
  return Object.values(TASKS).some((t) => t.doctor === doctorId && t.day === day && (slot == null || t.slot === slot));
}

export function dayAvailable(doctorId, day) {
  const dow = new Date(YEAR, MONTH, day).getDay();
  if (dow === 5) return false; // Friday: clinic closed
  if (isTaskBooking(doctorId, day)) return true; // task dates are always open
  const d = DOCTORS.findIndex((x) => x.id === doctorId);
  return hash(d + 1, day) % 4 !== 0; // about 1 in 4 days fully booked
}

export function slotAvailable(doctorId, day, slot) {
  if (isTaskBooking(doctorId, day, slot)) return true;
  const d = DOCTORS.findIndex((x) => x.id === doctorId);
  return hash(d * 31 + day, slot) % 3 !== 0; // about 1 in 3 slots taken
}

export const MONTHS = {
  en: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
  ar: ['كانون الثاني', 'شباط', 'آذار', 'نيسان', 'أيار', 'حزيران', 'تموز', 'آب', 'أيلول', 'تشرين الأول', 'تشرين الثاني', 'كانون الأول'],
};

export const WEEKDAYS = {
  en: ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
  ar: ['الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت'],
};

export const WEEKDAYS_SHORT = {
  en: ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'],
  ar: ['ح', 'ن', 'ث', 'ر', 'خ', 'ج', 'س'],
};

export const STRINGS = {
  en: {
    clinic: 'Al-Noor Family Clinic',
    clinic_sub: 'Book an appointment',
    fictional: 'Fictional clinic for a university study. No real bookings are made.',
    lang_toggle: 'عربي',
    lang_toggle_label: 'Switch to Arabic',
    task_title: 'Your task',
    task_card: 'Card',
    task_intro: 'Book this appointment:',
    task_spec: 'Specialty',
    task_doctor: 'Doctor',
    task_date: 'Date',
    task_time: 'Time',
    task_name: 'Name',
    task_phone: 'Phone',
    task_reason: 'Reason',
    step: 'Step {n} of 6',
    h_specialty: 'Choose a specialty',
    h_doctor: 'Choose a doctor',
    h_date: 'Choose a date',
    h_slot: 'Choose a time',
    h_form: 'Your details',
    h_confirm: 'Check and confirm',
    h_done: 'Appointment booked',
    years: '{n} years of experience',
    unavailable: 'not available',
    closed_note: 'The clinic is closed on Fridays. Grey days are fully booked.',
    slot_note: 'Grey times are already taken.',
    next: 'Next',
    back: 'Back',
    confirm: 'Confirm booking',
    f_name: 'Full name',
    f_phone: 'Phone number',
    f_reason: 'Reason for visit',
    f_required: 'Please fill in this field.',
    pick_first: 'Please make a choice first.',
    s_spec: 'Specialty',
    s_doctor: 'Doctor',
    s_date: 'Date',
    s_time: 'Time',
    s_name: 'Name',
    s_phone: 'Phone',
    done_text: 'Thank you. Your appointment is booked.',
    done_ref: 'Booking reference',
    done_tell: 'Please tell the researcher that you have finished.',
    no_session: 'Demo mode: nothing is being recorded.',
    selected: 'selected',
  },
  ar: {
    clinic: 'عيادة النور العائلية',
    clinic_sub: 'حجز موعد',
    fictional: 'عيادة وهمية لدراسة جامعية. لا يتم إجراء حجوزات حقيقية.',
    lang_toggle: 'EN',
    lang_toggle_label: 'Switch to English',
    task_title: 'مهمتك',
    task_card: 'البطاقة',
    task_intro: 'احجز هذا الموعد:',
    task_spec: 'التخصص',
    task_doctor: 'الطبيب',
    task_date: 'التاريخ',
    task_time: 'الوقت',
    task_name: 'الاسم',
    task_phone: 'الهاتف',
    task_reason: 'سبب الزيارة',
    step: 'الخطوة {n} من 6',
    h_specialty: 'اختر التخصص',
    h_doctor: 'اختر الطبيب',
    h_date: 'اختر التاريخ',
    h_slot: 'اختر الوقت',
    h_form: 'بياناتك',
    h_confirm: 'راجع وأكّد',
    h_done: 'تم حجز الموعد',
    years: 'خبرة {n} سنة',
    unavailable: 'غير متاح',
    closed_note: 'العيادة مغلقة يوم الجمعة. الأيام الرمادية محجوزة بالكامل.',
    slot_note: 'الأوقات الرمادية محجوزة.',
    next: 'التالي',
    back: 'رجوع',
    confirm: 'تأكيد الحجز',
    f_name: 'الاسم الكامل',
    f_phone: 'رقم الهاتف',
    f_reason: 'سبب الزيارة',
    f_required: 'يرجى تعبئة هذا الحقل.',
    pick_first: 'يرجى الاختيار أولاً.',
    s_spec: 'التخصص',
    s_doctor: 'الطبيب',
    s_date: 'التاريخ',
    s_time: 'الوقت',
    s_name: 'الاسم',
    s_phone: 'الهاتف',
    done_text: 'شكراً لك. تم حجز موعدك.',
    done_ref: 'رقم الحجز',
    done_tell: 'يرجى إخبار الباحث بأنك انتهيت.',
    no_session: 'وضع العرض: لا يتم تسجيل أي شيء.',
    selected: 'محدد',
  },
};

export function formatTime(min, lang) {
  const h24 = Math.floor(min / 60);
  const m = String(min % 60).padStart(2, '0');
  const h12 = ((h24 + 11) % 12) + 1;
  const suffix = h24 < 12 ? (lang === 'ar' ? 'ص' : 'AM') : (lang === 'ar' ? 'م' : 'PM');
  return `${h12}:${m} ${suffix}`;
}

export function formatDate(day, lang) {
  const dow = new Date(YEAR, MONTH, day).getDay();
  return `${WEEKDAYS[lang][dow]} ${day} ${MONTHS[lang][MONTH]} ${YEAR}`;
}
