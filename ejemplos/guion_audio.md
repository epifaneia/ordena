# Guiones para los audios de prueba

Grabados con el móvil, en andaluz, sin leer: la idea es decirlo como lo diría
un cliente, no como lo escribiría. Los nombres son de CRONUS, la empresa de
demostración de Business Central, para que la resolución contra maestros
tenga contra qué resolver.

Clientes de CRONUS: Trey Research, Adatum Corporation, School of Fine Art,
Alpine Ski House, Relecloud.

Artículos: silla giratoria LONDRES, silla giratoria MÚNICH, silla giratoria
MÉXICO, escritorio ATENAS, mesa de conferencias AMBERES, silla de invitados
PARÍS, lámpara AMSTERDAM, pizarra ATLANTA.

## Audio 1 · pedido más consulta (dos tickets)

> Hola, de parte de los de Trey Research. Ponme dos sillas giratorias de esas
> de Londres y una mesa de Amberes, para el jueves si puede ser. Y lo de los
> escritorios de Atenas del mes pasado, dime a cuánto estaban, porfa.

Esperado: un ticket de pedido (2 líneas, fecha relativa dudosa) y un ticket
de consulta con "se refiere a".

## Audio 2 · dos direcciones (dos pedidos)

> Mira, soy Jesse, de Relecloud. Me mandas tres lámparas de Amsterdam a la
> nave de Sevilla Este, y cinco sillas de Múnich, las amarillas, a la tienda
> de la calle Sierpes. Lo antes que puedas.

Esperado: dos tickets de pedido (cambia la dirección de entrega), fecha
ausente, incompleto por fecha.

## Audio 3 · modificación más queja

> Oye, lo de ayer, en vez de diez sillas de Londres ponme doce. Y el camión de
> la semana pasada llegó a las nueve de la noche, eso no puede ser.

Esperado: un ticket de modificación (se refiere a "lo de ayer", dudoso) y un
ticket de queja. Cliente sin resolver salvo que se pase `--remitente`.

## Audio 4 · ruido de fondo

El audio 1 grabado en la calle o con la radio puesta. Para ver qué marca
Whisper como dudoso.

## Audio 5 · sin cantidad y con unidad rara

> Los de Adatum. Mándales un palé de escritorios de Atenas y unas cuantas
> sillas de París. Para el quince.

Esperado: unidad "palé" no existe para el artículo (dudoso), cantidad de la
segunda línea ausente (incompleto), fecha "el quince" (primer día 15 futuro).

## Audio 6 · corrección a mitad y artículo que no existe

> Alpine Ski House, soy Ian. Ponme cuatro sillas de Tokio, las azules... no,
> mejor tres. Y dos de las sillas verdes de siempre, las que nos mandasteis
> en marzo. Referencia nuestra, la 4471. Para el 15 de octubre.

Esperado: cantidad 3 (no 4) en la primera línea; "sillas verdes de siempre"
dudosa con candidatos (ROMA verde, SÍDNEY verde), nunca un código inventado;
referencia 4471; fecha absoluta, segura.

## Audio 7 · precio y ruido

> Somos School of Fine Art. Cinco lámparas de Amsterdam a cincuenta como la
> otra vez, y que vaya bien, un abrazo.

Esperado: precio 50 distinto de la tarifa (55,20), dudoso; el saludo no
genera nada.

## Lista de campos: qué decir para que el sistema tenga motivo de sacarlos

| Campo | Qué decir | Qué debería pasar |
|---|---|---|
| Quién pide (empresa) | Un cliente de CRONUS, con naturalidad | Se resuelve a su número; a medias, dudoso con puntuación |
| Quién pide (persona) | Un nombre | Va a contacto, sin resolver |
| Qué | Artículos con las palabras deformadas de un cliente | Se resuelven a código; lo que no existe sale dudoso con candidatos |
| Cuánto | En letras y en cifras | Número; "unas cuantas" deja la línea sin cantidad e incompleto |
| Unidad | "un palé de", "tres cajas de", o nada | UDS por defecto; "palé" no existe para nadie: dudoso |
| Dónde | Dos sitios distintos en el mismo mensaje | Dos tickets; la dirección que no esté en la ficha, dudosa |
| Cuándo | Relativa, absoluta, vaga, o nada | Relativa: calculada y dudosa; absoluta: segura; vaga: dudosa; nada: incompleto |
| Referencia del cliente | "nuestro pedido es el 4471" | Va a referencia |
| Precio mencionado | "a ciento ochenta como la otra vez" | Si difiere de tarifa, dudoso; no se sobrescribe |
| Algo que no es pedido | Pregunta, queja, comentario | Ticket informativo aparte, con "se refiere a" si aplica |
| Modificación | "lo de ayer, en vez de diez ponme doce" | Ticket de modificación, "se refiere a" dudoso |
| Ruido | Saludos, despedidas | No genera nada |

Los nombres de `data/maestros_demo.json` son una aproximación. Tras ejecutar
`maestros` con Business Central, mirar `data/vocabulario.txt` para grabar
con los nombres reales. Para probar la vía del remitente conocido, pasar
`--remitente helen.ray@contoso.com` al procesar.
