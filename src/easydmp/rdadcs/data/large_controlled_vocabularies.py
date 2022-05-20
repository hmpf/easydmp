__all__ = [
    'Currency_ISO_4217',
    'Country_ISO_3166_1',
    'Language_ISO_639_3',
]


class Currency_ISO_4217:
    etype = 'currency'
    source = 'iso-4217'
    items = ['AED', 'AFN', 'ALL', 'AMD', 'ANG', 'AOA', 'ARS', 'AUD', 'AWG',
             'AZN', 'BAM', 'BBD', 'BDT', 'BGN', 'BHD', 'BIF', 'BMD', 'BND',
             'BOB', 'BRL', 'BSD', 'BTN', 'BWP', 'BYN', 'BZD', 'CAD', 'CDF',
             'CHF', 'CLP', 'CNY', 'COP', 'CRC', 'CUC', 'CUP', 'CVE', 'CZK',
             'DJF', 'DKK', 'DOP', 'DZD', 'EGP', 'ERN', 'ETB', 'EUR', 'FJD',
             'FKP', 'GBP', 'GEL', 'GGP', 'GHS', 'GIP', 'GMD', 'GNF', 'GTQ',
             'GYD', 'HKD', 'HNL', 'HRK', 'HTG', 'HUF', 'IDR', 'ILS', 'IMP',
             'INR', 'IQD', 'IRR', 'ISK', 'JEP', 'JMD', 'JOD', 'JPY', 'KES',
             'KGS', 'KHR', 'KMF', 'KPW', 'KRW', 'KWD', 'KYD', 'KZT', 'LAK',
             'LBP', 'LKR', 'LRD', 'LSL', 'LYD', 'MAD', 'MDL', 'MGA', 'MKD',
             'MMK', 'MNT', 'MOP', 'MRU', 'MUR', 'MVR', 'MWK', 'MXN', 'MYR',
             'MZN', 'NAD', 'NGN', 'NIO', 'NOK', 'NPR', 'NZD', 'OMR', 'PAB',
             'PEN', 'PGK', 'PHP', 'PKR', 'PLN', 'PYG', 'QAR', 'RON', 'RSD',
             'RUB', 'RWF', 'SAR', 'SBD', 'SCR', 'SDG', 'SEK', 'SGD', 'SHP',
             'SLL', 'SOS', 'SPL*', 'SRD', 'STN', 'SVC', 'SYP', 'SZL', 'THB',
             'TJS', 'TMT', 'TND', 'TOP', 'TRY', 'TTD', 'TVD', 'TWD', 'TZS',
             'UAH', 'UGX', 'USD', 'UYU', 'UZS', 'VEF', 'VND', 'VUV', 'WST',
             'XAF', 'XCD', 'XDR', 'XOF', 'XPF', 'YER', 'ZAR', 'ZMW', 'ZWD']


class Country_ISO_3166_1:
    etype = 'country'
    source = 'iso-3166-1'
    items = ['AD', 'AE', 'AF', 'AG', 'AI', 'AL', 'AM', 'AO', 'AQ', 'AR', 'AS',
             'AT', 'AU', 'AW', 'AX', 'AZ', 'BA', 'BB', 'BD', 'BE', 'BF', 'BG',
             'BH', 'BI', 'BJ', 'BL', 'BM', 'BN', 'BO', 'BQ', 'BR', 'BS', 'BT',
             'BV', 'BW', 'BY', 'BZ', 'CA', 'CC', 'CD', 'CF', 'CG', 'CH', 'CI',
             'CK', 'CL', 'CM', 'CN', 'CO', 'CR', 'CU', 'CV', 'CW', 'CX', 'CY',
             'CZ', 'DE', 'DJ', 'DK', 'DM', 'DO', 'DZ', 'EC', 'EE', 'EG', 'EH',
             'ER', 'ES', 'ET', 'FI', 'FJ', 'FK', 'FM', 'FO', 'FR', 'GA', 'GB',
             'GD', 'GE', 'GF', 'GG', 'GH', 'GI', 'GL', 'GM', 'GN', 'GP', 'GQ',
             'GR', 'GS', 'GT', 'GU', 'GW', 'GY', 'HK', 'HM', 'HN', 'HR', 'HT',
             'HU', 'ID', 'IE', 'IL', 'IM', 'IN', 'IO', 'IQ', 'IR', 'IS', 'IT',
             'JE', 'JM', 'JO', 'JP', 'KE', 'KG', 'KH', 'KI', 'KM', 'KN', 'KP',
             'KR', 'KW', 'KY', 'KZ', 'LA', 'LB', 'LC', 'LI', 'LK', 'LR', 'LS',
             'LT', 'LU', 'LV', 'LY', 'MA', 'MC', 'MD', 'ME', 'MF', 'MG', 'MH',
             'MK', 'ML', 'MM', 'MN', 'MO', 'MP', 'MQ', 'MR', 'MS', 'MT', 'MU',
             'MV', 'MW', 'MX', 'MY', 'MZ', 'NA', 'NC', 'NE', 'NF', 'NG', 'NI',
             'NL', 'NO', 'NP', 'NR', 'NU', 'NZ', 'OM', 'PA', 'PE', 'PF', 'PG',
             'PH', 'PK', 'PL', 'PM', 'PN', 'PR', 'PS', 'PT', 'PW', 'PY', 'QA',
             'RE', 'RO', 'RS', 'RU', 'RW', 'SA', 'SB', 'SC', 'SD', 'SE', 'SG',
             'SH', 'SI', 'SJ', 'SK', 'SL', 'SM', 'SN', 'SO', 'SR', 'SS', 'ST',
             'SV', 'SX', 'SY', 'SZ', 'TC', 'TD', 'TF', 'TG', 'TH', 'TJ', 'TK',
             'TL', 'TM', 'TN', 'TO', 'TR', 'TT', 'TV', 'TW', 'TZ', 'UA', 'UG',
             'UM', 'US', 'UY', 'UZ', 'VA', 'VC', 'VE', 'VG', 'VI', 'VN', 'VU',
             'WF', 'WS', 'YE', 'YT', 'ZA', 'ZM', 'ZW']


class Language_ISO_639_3:
    etype = 'language'
    source = 'iso-639-3'
    items = ['aar', 'abk', 'afr', 'aka', 'amh', 'ara', 'arg', 'asm', 'ava',
             'ave', 'aym', 'aze', 'bak', 'bam', 'bel', 'ben', 'bih', 'bis',
             'bod', 'bos', 'bre', 'bul', 'cat', 'ces', 'cha', 'che', 'chu',
             'chv', 'cor', 'cos', 'cre', 'cym', 'dan', 'deu', 'div', 'dzo',
             'ell', 'eng', 'epo', 'est', 'eus', 'ewe', 'fao', 'fas', 'fij',
             'fin', 'fra', 'fry', 'ful', 'gla', 'gle', 'glg', 'glv', 'grn',
             'guj', 'hat', 'hau', 'hbs', 'heb', 'her', 'hin', 'hmo', 'hrv',
             'hun', 'hye', 'ibo', 'ido', 'iii', 'iku', 'ile', 'ina', 'ind',
             'ipk', 'isl', 'ita', 'jav', 'jpn', 'kal', 'kan', 'kas', 'kat',
             'kau', 'kaz', 'khm', 'kik', 'kin', 'kir', 'kom', 'kon', 'kor',
             'kua', 'kur', 'lao', 'lat', 'lav', 'lim', 'lin', 'lit', 'ltz',
             'lub', 'lug', 'mah', 'mal', 'mar', 'mkd', 'mlg', 'mlt', 'mon',
             'mri', 'msa', 'mya', 'nau', 'nav', 'nbl', 'nde', 'ndo', 'nep',
             'nld', 'nno', 'nob', 'nor', 'nya', 'oci', 'oji', 'ori', 'orm',
             'oss', 'pan', 'pli', 'pol', 'por', 'pus', 'que', 'roh', 'ron',
             'run', 'rus', 'sag', 'san', 'sin', 'slk', 'slv', 'sme', 'smo',
             'sna', 'snd', 'som', 'sot', 'spa', 'sqi', 'srd', 'srp', 'ssw',
             'sun', 'swa', 'swe', 'tah', 'tam', 'tat', 'tel', 'tgk', 'tgl',
             'tha', 'tir', 'ton', 'tsn', 'tso', 'tuk', 'tur', 'twi', 'uig',
             'ukr', 'urd', 'uzb', 'ven', 'vie', 'vol', 'wln', 'wol', 'xho',
             'yid', 'yor', 'zha', 'zho', 'zul']
