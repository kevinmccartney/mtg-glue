# MTG Glue

A bunch of scripts I use to manage my MTG collection. Eventually they will probably live in the cloud & do scheduled exports/syncs/etc.

## Collection Management Strategy

### Current

- EchoMTG serves as the system of record
  - Tracks collection, prices & dates cards were acquired
- MoxField is for building lists
  - Tracks deck lists, buy list, folders of staple cards for decks
- Export EchoMTG => Run script to convert to Moxfield format => Import Moxfield

### Future

???

Probably lots of bullshit lol. I could do an overnight/manually triggered sync from Echo => Mox. Echo has an API

## Concepts in the ETL pipeline

- Rewrites: dynamically updates a field on all records. IE remove a set number if present in the card `name` field.
- Mappers: statically rewrite a field on all records. IE mapping a language code based on the language map in the config.
- Overrides: statically override a specfic card, identified by set name and card number. You can either override the card or split the card into two new records.
- Filters: filter out records from the final import file based on a criteria applied to each record.
