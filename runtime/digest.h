// SHA-1, SHA-256, SHA-512, MD5, HMAC and PBKDF2 in plain C++.
#pragma once
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>

namespace fathom_digest
{
	using Bytes = std::vector<uint8_t>;

	inline uint32_t rotl(uint32_t x, int n) { return (x << n) | (x >> (32 - n)); }
	inline uint32_t rotr(uint32_t x, int n) { return (x >> n) | (x << (32 - n)); }
	inline uint64_t rotr64(uint64_t x, int n) { return (x >> n) | (x << (64 - n)); }

	// padded to whole blocks
	inline Bytes padded(const uint8_t* data, size_t size, size_t block, size_t length_bytes, bool little)
	{
		Bytes m(data, data + size);
		m.push_back(0x80);
		while ((m.size() + length_bytes) % block)
			m.push_back(0);
		uint64_t bits = uint64_t(size) * 8;
		for (size_t k = 0; k < length_bytes; ++k)
		{
			size_t shift = little ? k : length_bytes - 1 - k;
			m.push_back(shift < 8 ? uint8_t(bits >> (8 * shift)) : 0);
		}
		return m;
	}

	inline uint32_t be32(const uint8_t* p) { return uint32_t(p[0]) << 24 | uint32_t(p[1]) << 16 | uint32_t(p[2]) << 8 | p[3]; }
	inline uint64_t be64(const uint8_t* p) { return uint64_t(be32(p)) << 32 | be32(p + 4); }
	inline uint32_t le32(const uint8_t* p) { return uint32_t(p[3]) << 24 | uint32_t(p[2]) << 16 | uint32_t(p[1]) << 8 | p[0]; }

	inline Bytes sha256(const uint8_t* data, size_t size)
	{
		static const uint32_t K[64] = {
			0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be,
			0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa,
			0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85,
			0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
			0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f,
			0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};
		uint32_t h[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
		Bytes m = padded(data, size, 64, 8, false);
		for (size_t at = 0; at < m.size(); at += 64)
		{
			uint32_t w[64];
			for (int i = 0; i < 16; ++i)
				w[i] = be32(&m[at + 4 * i]);
			for (int i = 16; i < 64; ++i)
			{
				uint32_t s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3);
				uint32_t s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10);
				w[i] = w[i - 16] + s0 + w[i - 7] + s1;
			}
			uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
			for (int i = 0; i < 64; ++i)
			{
				uint32_t t1 = hh + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i];
				uint32_t t2 = (rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c));
				hh = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
			}
			h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
		}
		Bytes out;
		for (uint32_t x : h)
			for (int k = 3; k >= 0; --k)
				out.push_back(uint8_t(x >> (8 * k)));
		return out;
	}

	inline Bytes sha512(const uint8_t* data, size_t size)
	{
		static const uint64_t K[80] = {
			0x428a2f98d728ae22, 0x7137449123ef65cd, 0xb5c0fbcfec4d3b2f, 0xe9b5dba58189dbbc, 0x3956c25bf348b538, 0x59f111f1b605d019,
			0x923f82a4af194f9b, 0xab1c5ed5da6d8118, 0xd807aa98a3030242, 0x12835b0145706fbe, 0x243185be4ee4b28c, 0x550c7dc3d5ffb4e2,
			0x72be5d74f27b896f, 0x80deb1fe3b1696b1, 0x9bdc06a725c71235, 0xc19bf174cf692694, 0xe49b69c19ef14ad2, 0xefbe4786384f25e3,
			0x0fc19dc68b8cd5b5, 0x240ca1cc77ac9c65, 0x2de92c6f592b0275, 0x4a7484aa6ea6e483, 0x5cb0a9dcbd41fbd4, 0x76f988da831153b5,
			0x983e5152ee66dfab, 0xa831c66d2db43210, 0xb00327c898fb213f, 0xbf597fc7beef0ee4, 0xc6e00bf33da88fc2, 0xd5a79147930aa725,
			0x06ca6351e003826f, 0x142929670a0e6e70, 0x27b70a8546d22ffc, 0x2e1b21385c26c926, 0x4d2c6dfc5ac42aed, 0x53380d139d95b3df,
			0x650a73548baf63de, 0x766a0abb3c77b2a8, 0x81c2c92e47edaee6, 0x92722c851482353b, 0xa2bfe8a14cf10364, 0xa81a664bbc423001,
			0xc24b8b70d0f89791, 0xc76c51a30654be30, 0xd192e819d6ef5218, 0xd69906245565a910, 0xf40e35855771202a, 0x106aa07032bbd1b8,
			0x19a4c116b8d2d0c8, 0x1e376c085141ab53, 0x2748774cdf8eeb99, 0x34b0bcb5e19b48a8, 0x391c0cb3c5c95a63, 0x4ed8aa4ae3418acb,
			0x5b9cca4f7763e373, 0x682e6ff3d6b2b8a3, 0x748f82ee5defb2fc, 0x78a5636f43172f60, 0x84c87814a1f0ab72, 0x8cc702081a6439ec,
			0x90befffa23631e28, 0xa4506cebde82bde9, 0xbef9a3f7b2c67915, 0xc67178f2e372532b, 0xca273eceea26619c, 0xd186b8c721c0c207,
			0xeada7dd6cde0eb1e, 0xf57d4f7fee6ed178, 0x06f067aa72176fba, 0x0a637dc5a2c898a6, 0x113f9804bef90dae, 0x1b710b35131c471b,
			0x28db77f523047d84, 0x32caab7b40c72493, 0x3c9ebe0a15c9bebc, 0x431d67c49c100d4c, 0x4cc5d4becb3e42b6, 0x597f299cfc657e2a,
			0x5fcb6fab3ad6faec, 0x6c44198c4a475817};
		uint64_t h[8] = {0x6a09e667f3bcc908, 0xbb67ae8584caa73b, 0x3c6ef372fe94f82b, 0xa54ff53a5f1d36f1,
						 0x510e527fade682d1, 0x9b05688c2b3e6c1f, 0x1f83d9abfb41bd6b, 0x5be0cd19137e2179};
		Bytes m = padded(data, size, 128, 16, false);
		for (size_t at = 0; at < m.size(); at += 128)
		{
			uint64_t w[80];
			for (int i = 0; i < 16; ++i)
				w[i] = be64(&m[at + 8 * i]);
			for (int i = 16; i < 80; ++i)
			{
				uint64_t s0 = rotr64(w[i - 15], 1) ^ rotr64(w[i - 15], 8) ^ (w[i - 15] >> 7);
				uint64_t s1 = rotr64(w[i - 2], 19) ^ rotr64(w[i - 2], 61) ^ (w[i - 2] >> 6);
				w[i] = w[i - 16] + s0 + w[i - 7] + s1;
			}
			uint64_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
			for (int i = 0; i < 80; ++i)
			{
				uint64_t t1 = hh + (rotr64(e, 14) ^ rotr64(e, 18) ^ rotr64(e, 41)) + ((e & f) ^ (~e & g)) + K[i] + w[i];
				uint64_t t2 = (rotr64(a, 28) ^ rotr64(a, 34) ^ rotr64(a, 39)) + ((a & b) ^ (a & c) ^ (b & c));
				hh = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
			}
			h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
		}
		Bytes out;
		for (uint64_t x : h)
			for (int k = 7; k >= 0; --k)
				out.push_back(uint8_t(x >> (8 * k)));
		return out;
	}

	inline Bytes sha1(const uint8_t* data, size_t size)
	{
		uint32_t h[5] = {0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476, 0xc3d2e1f0};
		Bytes m = padded(data, size, 64, 8, false);
		for (size_t at = 0; at < m.size(); at += 64)
		{
			uint32_t w[80];
			for (int i = 0; i < 16; ++i)
				w[i] = be32(&m[at + 4 * i]);
			for (int i = 16; i < 80; ++i)
				w[i] = rotl(w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16], 1);
			uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4];
			for (int i = 0; i < 80; ++i)
			{
				uint32_t f, k;
				if (i < 20) { f = (b & c) | (~b & d); k = 0x5a827999; }
				else if (i < 40) { f = b ^ c ^ d; k = 0x6ed9eba1; }
				else if (i < 60) { f = (b & c) | (b & d) | (c & d); k = 0x8f1bbcdc; }
				else { f = b ^ c ^ d; k = 0xca62c1d6; }
				uint32_t t = rotl(a, 5) + f + e + k + w[i];
				e = d; d = c; c = rotl(b, 30); b = a; a = t;
			}
			h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e;
		}
		Bytes out;
		for (uint32_t x : h)
			for (int k = 3; k >= 0; --k)
				out.push_back(uint8_t(x >> (8 * k)));
		return out;
	}

	inline Bytes md5(const uint8_t* data, size_t size)
	{
		static const uint32_t S[64] = {7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20,
									   4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21};
		static const uint32_t K[64] = {
			0xd76aa478, 0xe8c7b756, 0x242070db, 0xc1bdceee, 0xf57c0faf, 0x4787c62a, 0xa8304613, 0xfd469501, 0x698098d8, 0x8b44f7af, 0xffff5bb1,
			0x895cd7be, 0x6b901122, 0xfd987193, 0xa679438e, 0x49b40821, 0xf61e2562, 0xc040b340, 0x265e5a51, 0xe9b6c7aa, 0xd62f105d, 0x02441453,
			0xd8a1e681, 0xe7d3fbc8, 0x21e1cde6, 0xc33707d6, 0xf4d50d87, 0x455a14ed, 0xa9e3e905, 0xfcefa3f8, 0x676f02d9, 0x8d2a4c8a, 0xfffa3942,
			0x8771f681, 0x6d9d6122, 0xfde5380c, 0xa4beea44, 0x4bdecfa9, 0xf6bb4b60, 0xbebfbc70, 0x289b7ec6, 0xeaa127fa, 0xd4ef3085, 0x04881d05,
			0xd9d4d039, 0xe6db99e5, 0x1fa27cf8, 0xc4ac5665, 0xf4292244, 0x432aff97, 0xab9423a7, 0xfc93a039, 0x655b59c3, 0x8f0ccc92, 0xffeff47d,
			0x85845dd1, 0x6fa87e4f, 0xfe2ce6e0, 0xa3014314, 0x4e0811a1, 0xf7537e82, 0xbd3af235, 0x2ad7d2bb, 0xeb86d391};
		uint32_t h[4] = {0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476};
		Bytes m = padded(data, size, 64, 8, true);
		for (size_t at = 0; at < m.size(); at += 64)
		{
			uint32_t w[16];
			for (int i = 0; i < 16; ++i)
				w[i] = le32(&m[at + 4 * i]);
			uint32_t a = h[0], b = h[1], c = h[2], d = h[3];
			for (int i = 0; i < 64; ++i)
			{
				uint32_t f;
				int g;
				if (i < 16) { f = (b & c) | (~b & d); g = i; }
				else if (i < 32) { f = (d & b) | (~d & c); g = (5 * i + 1) % 16; }
				else if (i < 48) { f = b ^ c ^ d; g = (3 * i + 5) % 16; }
				else { f = c ^ (b | ~d); g = (7 * i) % 16; }
				uint32_t t = d;
				d = c; c = b; b = b + rotl(a + f + K[i] + w[g], S[i]); a = t;
			}
			h[0] += a; h[1] += b; h[2] += c; h[3] += d;
		}
		Bytes out;
		for (uint32_t x : h)
			for (int k = 0; k < 4; ++k)
				out.push_back(uint8_t(x >> (8 * k)));
		return out;
	}

	// kind: "sha256", "sha512", "sha1" or "md5"
	inline Bytes digest(const std::string& kind, const uint8_t* data, size_t size)
	{
		if (kind == "sha256") return sha256(data, size);
		if (kind == "sha512") return sha512(data, size);
		if (kind == "sha1") return sha1(data, size);
		if (kind == "md5") return md5(data, size);
		return {};
	}

	inline Bytes hmac(const std::string& kind, const uint8_t* key, size_t key_size, const uint8_t* data, size_t size)
	{
		size_t block = kind == "sha512" ? 128 : 64;
		Bytes k(key, key + key_size);
		if (k.size() > block)
			k = digest(kind, k.data(), k.size());
		k.resize(block, 0);
		Bytes inner(block), outer(block);
		for (size_t i = 0; i < block; ++i)
		{
			inner[i] = k[i] ^ 0x36;
			outer[i] = k[i] ^ 0x5c;
		}
		inner.insert(inner.end(), data, data + size);
		Bytes first = digest(kind, inner.data(), inner.size());
		outer.insert(outer.end(), first.begin(), first.end());
		return digest(kind, outer.data(), outer.size());
	}

	// PBKDF2 with HMAC-SHA256
	inline Bytes pbkdf2_sha256(const std::string& password, const uint8_t* salt, size_t salt_size, int rounds, size_t length)
	{
		const uint8_t* p = reinterpret_cast<const uint8_t*>(password.data());
		Bytes out;
		for (uint32_t block = 1; out.size() < length; ++block)
		{
			Bytes s(salt, salt + salt_size);
			for (int k = 3; k >= 0; --k)
				s.push_back(uint8_t(block >> (8 * k)));
			Bytes u = hmac("sha256", p, password.size(), s.data(), s.size()), t = u;
			for (int r = 1; r < rounds; ++r)
			{
				u = hmac("sha256", p, password.size(), u.data(), u.size());
				for (size_t i = 0; i < t.size(); ++i)
					t[i] ^= u[i];
			}
			out.insert(out.end(), t.begin(), t.end());
		}
		out.resize(length);
		return out;
	}
}
