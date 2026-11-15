
## Cómo funciona internamente

1. **`read_ar_members`** parsea el archivo `ar` del DEB, incluyendo el soporte de nombres largos (`//`) que usa Chrome.
2. **`decompress_member`** descomprime `control.tar.xz` (para leer la versión) y `data.tar.xz` (para extraer el `.so`). Soporta `.xz`, `.gz` y, de forma opcional, `.zst`.
3. **`extract_so`** recorre los miembros del tar buscando cualquier ruta que termine en `libwidevinecdm.so` y prioriza la que esté bajo `linux_x64` y `_platform_specific`.

## Aviso legal y descargo de responsabilidad

**Widevine CDM Grabber no está afiliado, patrocinado ni respaldado por Google LLC.**

- **Widevine** es una tecnología propietaria de Google. El archivo `libwidevinecdm.so` es software propietario de Google, no de código abierto, y se distribuye dentro del paquete oficial de Google Chrome.
- Esta herramienta **solo descarga el DEB oficial de Google** desde `dl.google.com` y **extrae** un archivo que ya viene incluido en él. No modifica el paquete, no descifra nada ni accede a contenido protegido.
- El uso de `libwidevinecdm.so` está sujeto a los **Términos de Servicio de Google Chrome** y a la legislación aplicable en materia de derechos de autor y protección de medidas tecnológicas (por ejemplo, la DMCA en EE. UU. o la Directiva 2001/29/CE en la UE).
- **Este software se proporciona "tal cual"**, sin garantías de ningún tipo, expresas o implícitas, incluidas, entre otras, las garantías de comerciabilidad, idoneidad para un fin concreto y no infracción.
- **En ningún caso** los autores o titulares de los derechos de autor serán responsables de ninguna reclamación, daño u otra responsabilidad, ya sea en una acción contractual, extracontractual o de otro tipo, que surja de, o esté relacionada con, el software o el uso u otras operaciones en el software.
- **Eres el único responsable** de asegurarte de que tu uso de esta herramienta y del archivo extraído cumple con las leyes de tu jurisdicción y con los términos de servicio de los servicios que utilices. No uses esta herramienta para eludir medidas de protección tecnológica con fines de infracción de derechos de autor.
- Si no estás de acuerdo con estos términos, **no uses esta herramienta**.

## Licencia

El código fuente de **Widevine CDM Grabber** se distribuye bajo la **licencia MIT**. Consulta el archivo `LICENSE` en la raíz del proyecto o visita <https://opensource.org/licenses/MIT>.

La licencia MIT **no se extiende** al archivo `libwidevinecdm.so` ni a Google Chrome, que son propiedad de Google LLC y están sujetos a sus propios términos.