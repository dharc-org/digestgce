
PUBLICATION_TYPES = ['Academic Journal Article',
 'Academic Journal Issue',
 'Report',
 'Book Chapter',
 'Book',
 'Doctoral Thesis']

def check_vocabulary(user_vocab, stable_vocab, column_name):
    for v in user_vocab:
        if v not in stable_vocab:
            print("Il valore "+v+" nella colonna "+column_name+" non è corretto. Sostituisci e ricarica il file")
