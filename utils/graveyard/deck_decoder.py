import base64
import re

# a python port of the decoder here: https://github.com/ValveSoftware/ArtifactDeckCode

s_nCurrentVersion = 2
sm_rgchEncodedPrefix = "ADC"
# returns { "heroes": [ {id, turn}, ... ] "cards": [ {id, count}, ... ] "name": name }
def ParseDeck(strDeckCode):
	deckBytes = DecodeDeckString(strDeckCode)
	if not deckBytes:
		return False
	deck = ParseDeckInternal(strDeckCode, deckBytes)
	return deck

def RawDeckBytes(strDeckCode):
	deckBytes = DecodeDeckString(strDeckCode)
	return deckBytes

def DecodeDeckString(strDeckCode):
	# check for prefix
	if strDeckCode[0:len(sm_rgchEncodedPrefix)] != sm_rgchEncodedPrefix:
		return False
	# strip prefix from deck code
	strNoPrefix = strDeckCode[len(sm_rgchEncodedPrefix):]
	#  deck strings are base64 but with url compatible strings, put the URL special chars back
	strNoPrefix = strNoPrefix.replace("-", "/")
	strNoPrefix = strNoPrefix.replace("_", "=")
	return base64.b64decode(strNoPrefix)

# reads out a var-int encoded block of bits, returns True if another chunk should follow
def ReadBitsChunk(nChunk, nNumBits, nCurrShift, nOutBits):
	nContinueBit = 1 << nNumBits
	nNewBits = nChunk & (nContinueBit - 1)
	nOutBits |= nNewBits << nCurrShift
	return (nChunk & nContinueBit) != 0, nOutBits

def ReadVarEncodedUint32(nBaseValue, nBaseBits, data, indexStart, indexEnd, outValue):
	outValue = 0
	nDeltaShift = 0
	success, outValue = ReadBitsChunk(nBaseValue, nBaseBits, nDeltaShift, outValue)
	if nBaseBits == 0 or success:
		nDeltaShift += nBaseBits
		while True:
			# do we have more room?
			if indexStart > indexEnd:
				return False, indexStart, outValue
			# read the bits from this next byte and see if we are done
			nNextByte = data[indexStart]
			indexStart += 1
			success, outValue = ReadBitsChunk(nNextByte, 7, nDeltaShift, outValue)
			if not success:
				break
			nDeltaShift += 7
	return True, indexStart, outValue

	
# handles decoding a card that was serialized
def ReadSerializedCard(data, indexStart, indexEnd, nPrevCardBase):
	nOutCount = 0
	nOutCardID = 0
	# end of the memory block?
	if indexStart > indexEnd:
		return False
	# header contains the count (2 bits), a continue flag, and 5 bits of offset data. If we have 11 for the count bits we have the count
	# encoded after the offset
	nHeader = data[indexStart]
	indexStart += 1
	bHasExtendedCount = ( nHeader >> 6) == 0x03
	# read in the delta, which has 5 bits in the header, then additional bytes while the value is set
	nCardDelta = 0
	success, indexStart, nCardDelta = ReadVarEncodedUint32(nHeader, 5, data, indexStart, indexEnd, nCardDelta)
	if not success:
		return False, indexStart, indexEnd, nPrevCardBase, nOutCount, nOutCardID
	nOutCardID = nPrevCardBase + nCardDelta
	# now parse the count if we have an extended count
	if bHasExtendedCount:
		success, indexStart, nOutCount = ReadVarEncodedUint32(0, 0, data, indexStart, indexEnd, nOutCount)
		if not success:
			return False, indexStart, indexEnd, nPrevCardBase, nOutCount, nOutCardID
	else:
		# the count is just the upper two bits + 1 (since we don't encode zero)
		nOutCount = (nHeader >> 6) + 1
	# update our previous card before we do the remap, since it was encoded without the remap
	nPrevCardBase = nOutCardID
	return True, indexStart, nPrevCardBase, nOutCount, nOutCardID

def ParseDeckInternal(strDeckCode, deckBytes):
	nCurrentByteIndex = 0
	nTotalBytes = len(deckBytes)
	# check version num
	nVersionAndHeroes = deckBytes[nCurrentByteIndex]
	nCurrentByteIndex += 1
	version = nVersionAndHeroes >> 4
	if s_nCurrentVersion != version and version != 1:
		return False
	# do checksum check
	nChecksum = deckBytes[nCurrentByteIndex]
	nCurrentByteIndex += 1
	nStringLength = 0
	if version > 1:
		nStringLength = deckBytes[nCurrentByteIndex]
		nCurrentByteIndex += 1
	nTotalCardBytes = nTotalBytes - nStringLength
	# grab the string size

	nComputedChecksum = 0
	for i in range(nCurrentByteIndex, nTotalCardBytes):
		nComputedChecksum += deckBytes[i]
	masked = nComputedChecksum & 0xFF
	if nChecksum != masked:
		return False

	# read in our hero count (part of the bits are in the version, but we can overflow bits here
	nNumHeroes = 0
	success, indexStart, nNumHeroes = ReadVarEncodedUint32(nVersionAndHeroes, 3, deckBytes, nCurrentByteIndex, nTotalCardBytes, nNumHeroes)
	if not success:
		return False
	# now read in the heroes
	heroes = []

	nPrevCardBase = 0
	for nCurrHero in range(nNumHeroes):
		success, nCurrentByteIndex, nPrevCardBase, nHeroTurn, nHeroCardID = ReadSerializedCard(deckBytes, nCurrentByteIndex, nTotalCardBytes, nPrevCardBase)
		if not success:
			return False
		heroes.append({ "id": nHeroCardID, "turn": nHeroTurn })

	cards = []
	nPrevCardBase = 0
	#  1 indexed - change to nCurrentByteIndex < nTotalCardBytes if 0 indexed
	while nCurrentByteIndex <= nTotalCardBytes:
		success, nCurrentByteIndex, nPrevCardBase, nCardCount, nCardID = ReadSerializedCard(deckBytes, nCurrentByteIndex, nTotalBytes, nPrevCardBase)
		if not success:
			return False
		cards.append({ "id": nCardID, "count": nCardCount })

	name = ""
	if nCurrentByteIndex <= nTotalBytes:
		bytesList = deckBytes[-1 * nStringLength:]
		name = "".join(map(chr, bytesList))
		#  replace strip_tags with an HTML sanitizer or escaper as needed.
		name = re.sub(r"<[^>]*?>", "", name)

	return { "heroes": heroes, "cards": cards, "name": name }

